// Which on-device engine serves each language on this Mac. There is no cloud speech: audio stays here. A language Apple
// supports but hasn't installed is downloaded; one it can't serve falls back to English, and Settings and the bar say so.
import AVFoundation
import Foundation
import Speech

enum SpeechLocale {
    struct Pick { let locale: Locale, engine: String }   // engine: "speech" (SpeechTranscriber) or "dictation" (DictationTranscriber)
    // First match wins. en-IN before en-US: an Indian accent is what this Mac will hear.
    static let wanted = ["en": ["en-IN", "en-US"], "hi": ["hi-IN"]]
    static let english = Pick(locale: Locale(identifier: "en-US"), engine: "speech")   // installed with macOS; the base app's only locale
    static var picks: [String: Pick] = [:]
    static var status: [String: [String: Any]] = [:]
    static var refreshing = false, again = false

    // Never throws or blocks: before the first probe, and for anything missing, it is English ("unsupported locale" killed every ask in 1.5.0).
    static func current(_ lang: String) -> Pick { picks[lang] ?? picks["en"] ?? english }

    static func bcp47(_ locales: [Locale]) -> Set<String> { Set(locales.map { $0.identifier(.bcp47) }) }

    // Pure, so a test can run it: the first wanted locale installed for either engine, else the first that can be downloaded.
    static func choose(_ tags: [String], speech: Set<String>, speechInstalled: Set<String>, dictation: Set<String>, dictationInstalled: Set<String>) -> (tag: String, engine: String, state: String)? {
        for t in tags { if speechInstalled.contains(t) { return (t, "speech", "ready") }; if dictationInstalled.contains(t) { return (t, "dictation", "ready") } }
        for t in tags { if speech.contains(t) { return (t, "speech", "downloading") }; if dictation.contains(t) { return (t, "dictation", "downloading") } }
        return nil
    }

    // At launch and when the language changes: probe, fetch what's missing, write speech.json, tell an open Settings.
    static func refresh() {
        guard !refreshing else { again = true; return }
        refreshing = true
        Task {
            let speech = bcp47(await SpeechTranscriber.supportedLocales), speechInstalled = bcp47(await SpeechTranscriber.installedLocales)
            let dictation = bcp47(await DictationTranscriber.supportedLocales), dictationInstalled = bcp47(await DictationTranscriber.installedLocales)
            var missing: [(lang: String, tag: String, engine: String)] = []
            await MainActor.run {
                for (lang, tags) in wanted {
                    guard let c = choose(tags, speech: speech, speechInstalled: speechInstalled, dictation: dictation, dictationInstalled: dictationInstalled) else {
                        status[lang] = ["state": "missing", "engine": "", "locale": ""]; picks[lang] = nil; continue
                    }
                    status[lang] = ["state": c.state, "engine": c.engine, "locale": c.tag, "progress": 0.0]
                    if c.state == "ready" { picks[lang] = Pick(locale: Locale(identifier: c.tag), engine: c.engine) } else { missing.append((lang, c.tag, c.engine)) }
                }
                publish(); app.prepareSpeech()
            }
            for item in missing { await install(item.lang, item.tag, item.engine) }
            await MainActor.run {
                refreshing = false
                if again { again = false; refresh() }
            }
        }
    }

    static func module(_ tag: String, _ engine: String) -> any SpeechModule {
        let locale = Locale(identifier: tag)
        return engine == "dictation" ? DictationTranscriber(locale: locale, preset: .progressiveShortDictation) : SpeechTranscriber(locale: locale, preset: .progressiveTranscription)
    }

    static func install(_ lang: String, _ tag: String, _ engine: String) async {
        do {
            if let request = try await AssetInventory.assetInstallationRequest(supporting: [module(tag, engine)]) {
                let watch = Task {
                    while !Task.isCancelled {
                        let done = request.progress.fractionCompleted
                        await MainActor.run { status[lang]?["progress"] = done; publish() }
                        try? await Task.sleep(for: .seconds(1))
                    }
                }
                defer { watch.cancel() }
                try await request.downloadAndInstall()
            }
            await MainActor.run {
                status[lang] = ["state": "ready", "engine": engine, "locale": tag, "progress": 1.0]
                picks[lang] = Pick(locale: Locale(identifier: tag), engine: engine)
                publish(); app.prepareSpeech()
            }
        } catch {
            await MainActor.run { status[lang] = ["state": "missing", "engine": "", "locale": ""]; publish() }
        }
    }

    // `Chiron --speech-file <audio> <en|hi>`: the same engine and locale a voice ask gets, on a file. For `chiron.py --speech-eval`.
    static func transcribe(_ path: String, _ lang: String) async -> (text: String, engine: String)? {
        let speech = bcp47(await SpeechTranscriber.installedLocales), dictation = bcp47(await DictationTranscriber.installedLocales)
        guard let tags = wanted[lang], let c = choose(tags, speech: speech, speechInstalled: speech, dictation: dictation, dictationInstalled: dictation),
              let file = try? AVAudioFile(forReading: URL(fileURLWithPath: path)) else { return nil }
        let locale = Locale(identifier: c.tag)
        do {
            if c.engine == "dictation" {
                let t = DictationTranscriber(locale: locale, preset: .progressiveShortDictation), analyzer = SpeechAnalyzer(modules: [t])
                let reading = Task { var out = ""; for try await r in t.results where r.isFinal { out += String(r.text.characters) }; return out }
                try await analyzer.start(inputAudioFile: file, finishAfterFile: true)
                return (try await reading.value, c.engine)
            }
            let t = SpeechTranscriber(locale: locale, preset: .transcription), analyzer = SpeechAnalyzer(modules: [t])
            // The same hint a live ask gets: this Mac's app names and the user's dictionary.
            let ctx = AnalysisContext(); ctx.contextualStrings[.general] = appHints(); try? await analyzer.setContext(ctx)
            let reading = Task { var out = ""; for try await r in t.results where r.isFinal { out += String(r.text.characters) }; return out }
            try await analyzer.start(inputAudioFile: file, finishAfterFile: true)
            return (try await reading.value, c.engine)
        } catch { return nil }
    }

    static func appHints() -> [String] {
        let apps = [NSHomeDirectory() + "/Applications", "/Applications", "/System/Applications", "/System/Applications/Utilities"].flatMap {
            ((try? FileManager.default.contentsOfDirectory(atPath: $0)) ?? []).filter { $0.hasSuffix(".app") }.map { String($0.dropLast(4)) }
        }
        return DictationData.words + apps.prefix(100)
    }

    static func publish() {
        home.push("speech", status)
        let folder = (Prefs.path as NSString).deletingLastPathComponent
        if let data = try? JSONSerialization.data(withJSONObject: status, options: [.sortedKeys]) { try? data.write(to: URL(fileURLWithPath: folder + "/speech.json"), options: .atomic) }
    }
}

// voice.jsonl: one row per voice ask, for Home. A later row with the same id replaces it (see chiron/home.py).
enum VoiceLog {
    static var last: (id: String, at: String, lang: String, engine: String, words: Int, seconds: Double, key: String, when: Date)?
    static var path: String { (Prefs.path as NSString).deletingLastPathComponent + "/voice.jsonl" }
    static func write(_ row: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: row), let handle = FileHandle(forWritingAtPath: path) ?? {
            FileManager.default.createFile(atPath: path, contents: nil, attributes: [.posixPermissions: 0o600]); return FileHandle(forWritingAtPath: path) }() else { return }
        defer { try? handle.close() }
        _ = try? handle.seekToEnd(); try? handle.write(contentsOf: data + Data("\n".utf8))
    }
    static func row(_ l: (id: String, at: String, lang: String, engine: String, words: Int, seconds: Double, key: String, when: Date), understood: Bool) -> [String: Any] {
        ["id": l.id, "at": l.at, "lang": l.lang, "engine": l.engine, "words": l.words, "seconds": (l.seconds * 10).rounded() / 10, "understood": understood]
    }
    // An ask repeated within 10 s wasn't understood the first time.
    static func add(_ text: String, seconds: Double) {
        let key = transcriptKey(text), words = text.split(whereSeparator: { $0.isWhitespace }).count
        guard words > 0 else { return }
        if let l = last, l.key == key, Date().timeIntervalSince(l.when) < 10 { write(row(l, understood: false)) }
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        let lang = Strings.lang, new = (id: UUID().uuidString, at: f.string(from: Date()), lang: lang, engine: SpeechLocale.current(lang).engine, words: words, seconds: seconds, key: key, when: Date())
        last = new; write(row(new, understood: true))
    }
    // Cancelled within 10 s: the same.
    static func cancelled() {
        guard let l = last, Date().timeIntervalSince(l.when) < 10 else { return }
        write(row(l, understood: false)); last = nil
    }
}
