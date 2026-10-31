// The page's one message handler, `home`: bridge.call(method, args) posts {id, method, args}; the answer goes back
// with bridge.reply(id, result, error). Native things (Keychain, permissions, windows) are answered here;
// the rest by `chiron.py --home-state` and `chiron.py --home-do <method>` (JSON args on stdin, JSON on stdout).
import AVFoundation
import Carbon
import Cocoa
import WebKit

final class HomeBridge: NSObject, WKScriptMessageHandler {
    private var pages: [ObjectIdentifier: WKWebView] = [:]

    func attach(_ web: WKWebView) { pages[ObjectIdentifier(web)] = web }
    func detach(_ web: WKWebView?) { if let web { pages[ObjectIdentifier(web)] = nil } }

    // Prefs the page may write. Anything else (paused, safe, hotkeys) keeps its own native path.
    static let writable: Set<String> = ["lang", "cap", "brain", "apiBase", "apiModel", "jevBase", "openaiModel", "theme", "talkKey", "speak", "speakRate", "voice.en", "voice.hi", "ttsVoice.en", "ttsVoice.hi", "appleVoice"]
    // The page's names for prefs whose stored key predates it (apiBase/apiModel).
    static let aliases = ["capUsd": "cap", "customUrl": "apiBase", "customModel": "apiModel", "jevBaseUrl": "jevBase"]
    // Changing these must not reuse a Claude worker started with the old brain or key.
    static let restartsWorker: Set<String> = ["brain", "apiBase", "apiModel"]

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let body = m.body as? [String: Any], let id = body["id"], let method = body["method"] as? String,
              let web = m.webView else { return }
        let args = body["args"] as? [String: Any] ?? [:]
        let reply: (Any?, String?) -> Void = { result, error in
            callJS(web, "bridge.reply", [id, result ?? NSNull(), error.map { $0 as Any } ?? NSNull()])
        }
        handle(method, args, reply)
    }

    func handle(_ method: String, _ args: [String: Any], _ reply: @escaping (Any?, String?) -> Void) {
        switch method {
        case "state.get":
            homeState { reply($0, nil) }
        case "strings.get":
            let lang = args["lang"] as? String ?? Strings.lang
            reply(Strings.all(["en", "hi"].contains(lang) ? lang : "en"), nil)
        case "app.info":
            let info = Bundle.main.infoDictionary ?? [:]
            reply(["version": info["CFBundleShortVersionString"] as? String ?? "dev", "build": info["CFBundleVersion"] as? String ?? "0",
                   "commit": info["ChironCommit"] as? String ?? ""], nil)
        case "lang.set":
            guard let lang = args["lang"] as? String, ["en", "hi"].contains(lang) else { return reply(nil, "bad lang") }
            Prefs.set("lang", lang)
            home.push("lang", lang)   // every open page re-labels; menus read L() each time they open
            voiceBar.relabel(); app.prepareSpeech()
            home.refresh()
            reply(["ok": true], nil)
        case "prefs.get":
            if let k = args["k"] as? String { return reply(["k": k, "v": Prefs.d[HomeBridge.aliases[k] ?? k] ?? NSNull()], nil) }
            var out: [String: Any] = Dictionary(uniqueKeysWithValues: HomeBridge.writable.map { ($0, Prefs.d[$0] ?? NSNull()) })
            for (page, stored) in HomeBridge.aliases { out[page] = Prefs.d[stored] ?? NSNull() }
            if out["capUsd"] is NSNull { out["capUsd"] = 5 }
            // Read-only: the page shows the real shortcuts in its greeting and Settings.
            out["hotkeyLabel"] = Prefs.str("hotkeyLabel")
            out["dictateHotkeyLabel"] = Prefs.bool("dictateHotkeyOff") ? "" : Prefs.str("dictateHotkeyLabel")
            out["globeTaken"] = globeKeyTaken()
            reply(out, nil)
        case "prefs.set":
            guard let asked = args["k"] as? String, let v = args["v"] else { return reply(["ok": false], nil) }
            let k = HomeBridge.aliases[asked] ?? asked
            guard HomeBridge.writable.contains(k) else { return reply(["ok": false], nil) }
            if k == "brain", !["claude-code", "anthropic", "openai", "custom"].contains(v as? String ?? "") { return reply(["ok": false], nil) }
            if k == "theme", !["system", "light", "dark"].contains(v as? String ?? "") { return reply(["ok": false], nil) }
            if k == "cap", let n = (v as? NSNumber)?.doubleValue { Prefs.set(k, min(50, max(1, n))) } else { Prefs.set(k, v) }
            if HomeBridge.restartsWorker.contains(k) { app.unwarm() }
            if k == "theme" { home.applyTheme() }
            if k == "talkKey" {   // modifiers alone: code -2 goes through the event monitor, like fn always has
                let fn = v as? String == "fn"
                Prefs.set("hotkeyCode", -2); Prefs.set("hotkeyMods", fn ? chironFnKey : controlKey | optionKey); Prefs.set("hotkeyLabel", fn ? "fn" : "⌃⌥")
                registerHotkey()
            }
            reply(["ok": true], nil)
        case "brain.choose":
            handle("prefs.set", ["k": "brain", "v": args["kind"] ?? ""], reply)
        case "conn.list":
            var out: [String: Any] = [:]
            for name in ["anthropic", "openai", "jev", "custom", "google"] { out[name] = Keychain.masked(name) }
            var jev = out["jev"] as? [String: Any] ?? [:]; jev["base_url"] = Prefs.str("jevBase"); out["jev"] = jev
            var custom = out["custom"] as? [String: Any] ?? [:]; custom["url"] = Prefs.str("apiBase"); custom["model"] = Prefs.str("apiModel"); out["custom"] = custom
            out["brain"] = Prefs.str("brain").isEmpty ? "claude-code" : Prefs.str("brain")
            reply(out, nil)
        case "conn.save":
            guard let name = args["name"] as? String, let value = args["value"] as? String, Keychain.set(name, value) else { return reply(["ok": false], nil) }
            if name == "anthropic" || name == "custom" { app.unwarm() }
            reply(["ok": true, "last4": String(value.trimmingCharacters(in: .whitespacesAndNewlines).suffix(4))], nil)
        case "conn.clear":
            guard let name = args["name"] as? String else { return reply(["ok": false], nil) }
            let ok = Keychain.delete(name)
            if name == "anthropic" || name == "custom" { app.unwarm() }
            reply(["ok": ok], nil)
        case "conn.test":
            HomeBridge.python(["--home-do", "conn.test"], args) { [weak self] r in
                reply(r ?? ["ok": false, "detail": L("conn.result.server"), "ms": 0, "usd": 0], nil)
                self?.homeState { home.push("connection", ($0 as? [String: Any])?["connections"] ?? [:]) }
            }
        case "claudeCode.status":
            Onboarding.plan { c in
                let need = c["need"] as? String ?? ""
                reply(["installed": need != "install", "signedIn": need != "install" && need != "login",
                       "plan": c["tier"] as? String ?? "", "ok": c["ok"] as? Bool ?? false,
                       "text": c["text"] as? String ?? ""], nil)
            }
        case "claudeCode.setup":
            onboarding.fixPlan()
            reply(["ok": true], nil)
        case "local.scan":
            detectLocalServers { found in
                reply(found.map { ["name": $0["name"] ?? "", "url": $0["base"] ?? "", "models": $0["models"] ?? []] }, nil)
            }
        case "perms.get":
            DispatchQueue.global().async {
                let p = Onboarding.perms()
                let s: (String) -> String = { p[$0] == true ? "granted" : "denied" }
                let out = ["microphone": s("mic"), "speech": s("speech"), "accessibility": s("ax"), "screen": s("screen"), "automation": s("auto")]
                DispatchQueue.main.async { reply(out, nil) }
            }
        case "perms.grant":
            let ids = ["microphone": "mic", "speech": "speech", "accessibility": "ax", "screen": "screen", "automation": "auto"]
            guard let id = args["id"] as? String, let native = ids[id] else { return reply(["ok": false], nil) }
            onboarding.grant(native)
            reply(["ok": true], nil)
        case "window.settings":   // older callers; Settings is a sheet inside the page now
            home.openSettings(); reply(["opened": true], nil)
        case "dictionary.list":   // the words dictation must spell right, and the heard forms Chiron learned for them
            reply(["words": DictationData.words, "fixes": DictationData.fixes], nil)
        case "dictionary.add":
            guard let word = args["word"] as? String else { return reply(["ok": false], nil) }
            reply(["ok": DictationData.word(word)], nil)
        case "dictionary.remove":
            guard let word = args["word"] as? String else { return reply(["ok": false], nil) }
            reply(["ok": DictationData.forget(word)], nil)
        case "ask.start":   // Home's Ask button: the same box and listening as the shortcut or the menu's Ask
            app.clickTalk = true; app.start(); if !app.engine.isRunning { app.clickTalk = false }
            reply(["ok": true], nil)
        case "conversations.list":
            HomeBridge.python(["--home-do", method], args) { reply($0 ?? [:], nil) }
        case "conversations.delete":
            HomeBridge.python(["--home-do", method], args) { reply($0 ?? ["ok": false], nil) }
        case "conversations.clear":
            HomeBridge.python(["--home-do", method], args) { reply($0 ?? ["ok": false], nil) }
        case "ask.again":
            guard let text = args["text"] as? String, !text.isEmpty, !app.busy, !app.engine.isRunning else { return reply(["ok": false], nil) }
            app.typed(text, keep: true); reply(["ok": true], nil)
        case "clipboard.copy":
            guard let text = args["text"] as? String else { return reply(["ok": false], nil) }
            NSPasteboard.general.clearContents(); NSPasteboard.general.setString(text, forType: .string); reply(["ok": true], nil)
        case "speech.status":
            reply(SpeechLocale.status, nil)
        case "speech.test":
            let lang = ["en", "hi"].contains(args["lang"] as? String ?? "") ? args["lang"] as! String : "en"
            app.testVoice(lang) { heard in reply(["text": heard, "engine": SpeechLocale.current(lang).engine], nil) }
        case "voices.list":
            var out: [String: [[String: String]]] = ["en": [], "hi": []]
            for v in AVSpeechSynthesisVoice.speechVoices() where installedSayVoices?.contains(v.name) ?? true {
                let code = String(v.language.prefix(2))
                if out[code] != nil { out[code]?.append(["id": v.name, "name": v.name + " (" + v.language + ")"]) }
            }
            reply(out, nil)
        case "voices.preview":
            let lang = ["en", "hi"].contains(args["lang"] as? String ?? "") ? args["lang"] as! String : "en"
            let line = Strings.table(lang)["voice.preview"] ?? ""
            let chosen = args["id"] as? String ?? "", rate = (args["rate"] as? NSNumber)?.doubleValue
            app.shush()
            let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            p.arguments = readAloudArguments(line, pick: { chosen.isEmpty ? usableReadAloudVoice($0) : chosen }, rate: sayRate(rate)) {}
            try? p.run(); app.voice = p
            reply(["ok": true], nil)
        case "tts.preview":
            let lang = ["en", "hi"].contains(args["lang"] as? String ?? "") ? args["lang"] as! String : "en"
            app.speakCloud(Strings.table(lang)["voice.preview"] ?? "", lang: lang, voice: args["voice"] as? String)
            reply(["ok": true], nil)
        case "globe.fix":
            Chiron.settings.handle(["do": "globeKey"]); reply(["ok": true], nil)
        case "bar.reset":
            voiceBar.reset(); reply(["ok": true], nil)
        case "link.open":   // the page never navigates itself; only web links leave, in the default browser
            guard let s = args["url"] as? String, let url = URL(string: s), url.scheme == "https" else { return reply(["ok": false], nil) }
            NSWorkspace.shared.open(url); reply(["ok": true], nil)
        case "window.home":
            home.openHome(); reply(["ok": true], nil)
        default:
            reply(nil, "unknown method \(method)")
        }
    }

    func homeState(_ done: @escaping (Any) -> Void) {
        HomeBridge.python(["--home-state"], nil) { done($0 ?? [:]) }
    }

    // chiron.py off the main thread; a crash or bad JSON answers nil rather than hanging the page.
    static func python(_ args: [String], _ input: [String: Any]?, _ done: @escaping ([String: Any]?) -> Void) {
        DispatchQueue.global().async {
            let p = py(args), out = Pipe(), inp = Pipe()
            p.standardOutput = out; p.standardInput = inp; p.standardError = FileHandle.nullDevice
            do { try p.run() } catch { DispatchQueue.main.async { done(nil) }; return }
            let data = input.flatMap { try? JSONSerialization.data(withJSONObject: $0) } ?? Data("{}".utf8)
            inp.fileHandleForWriting.write(data); try? inp.fileHandleForWriting.close()
            let result = out.fileHandleForReading.readDataToEndOfFile(); p.waitUntilExit()
            let json = (try? JSONSerialization.jsonObject(with: result)) as? [String: Any]
            DispatchQueue.main.async { done(json) }
        }
    }
}
