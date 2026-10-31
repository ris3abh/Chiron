// The always-on Voice Bar: a small pill on every desktop that shows what Chiron is doing, and the card above it for what
// needs more room: long answers, Allow, choices, rewrites, typed replies. App still drives ui/ui.html, now never on screen,
// as its state machine; every call to it also comes here (mirror), and the card's buttons send the same messages back.
import Cocoa
import WebKit

// Never takes focus from the app the user is talking about, unless a card is open and they click into it.
final class BarPanel: NSPanel { var takesKeys = false; override var canBecomeKey: Bool { takesKeys } }

// The web view draws; this transparent layer over it takes the mouse, so a click can never reach the page or activate Chiron.
final class BarHandle: NSView {
    var start: NSPoint?, moved = false
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with e: NSEvent) {
        if e.clickCount == 2 { voiceBar.reset(); start = nil; return }
        start = NSEvent.mouseLocation; moved = false
    }
    override func mouseDragged(with e: NSEvent) {
        guard let start, let w = window else { return }
        let now = NSEvent.mouseLocation
        w.setFrameOrigin(NSPoint(x: w.frame.origin.x + now.x - start.x, y: w.frame.origin.y + now.y - start.y))
        self.start = now; moved = true
    }
    override func mouseUp(with e: NSEvent) { if moved { voiceBar.remember() }; start = nil }
    override func rightMouseDown(with e: NSEvent) { NSMenu.popUpContextMenu(voiceBar.menu(), with: e, for: self) }
}

final class VoiceBar: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
    static let width: CGFloat = 56, height: CGFloat = 20, margin: CGFloat = 16
    let panel = BarPanel(contentRect: NSRect(x: 0, y: 0, width: VoiceBar.width, height: VoiceBar.height), styleMask: [.nonactivatingPanel, .borderless], backing: .buffered, defer: false)
    let web: WKWebView
    var loaded = false, pending: [(String, [Any])] = [], settle: DispatchWorkItem?
    var handle: BarHandle?, cardKind = "", cardClose: DispatchWorkItem?, lastStep = ""
    var cardOpen: Bool { !cardKind.isEmpty }

    override init() {
        let cfg = WKWebViewConfiguration()
        web = WKWebView(frame: panel.contentRect(forFrameRect: panel.frame), configuration: cfg)
        super.init()
        cfg.userContentController.add(self, name: "bar")
        web.navigationDelegate = self; web.setValue(false, forKey: "drawsBackground"); web.autoresizingMask = [.width, .height]
        panel.isOpaque = false; panel.backgroundColor = .clear; panel.hasShadow = false; panel.hidesOnDeactivate = false
        panel.level = .statusBar; panel.isReleasedWhenClosed = false
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        applySharing(panel)
        let root = NSView(frame: web.frame); root.autoresizingMask = [.width, .height]
        let handle = BarHandle(frame: root.bounds)
        root.addSubview(web); root.addSubview(handle); panel.contentView = root
        self.handle = handle
        let ui = URL(fileURLWithPath: dir + "/ui", isDirectory: true)
        web.loadFileURL(ui.appendingPathComponent("bar.html"), allowingReadAccessTo: ui)
    }

    func start() { place(on: mouseScreen); sync() }
    // Always visible unless paused.
    func sync() { if Prefs.bool("paused") { panel.orderOut(nil) } else { panel.orderFrontRegardless() } }

    private func call(_ fn: String, _ args: [Any]) {
        if loaded { callJS(web, "bar." + fn, args) } else { pending.append((fn, args)) }
    }
    func relabel() { call("strings", [Strings.table(Strings.lang), Strings.lang]) }
    func webView(_ v: WKWebView, didFinish n: WKNavigation!) {
        loaded = true; relabel()
        pending.forEach { callJS(web, "bar." + $0.0, $0.1) }; pending = []
    }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let body = m.body as? [String: Any] else { return }
        if let a = body["act"] as? [String: Any] { app.boxAction(a) }
        if body["close"] != nil { closeCard(); app.cardClosed() }
        if body["key"] != nil { panel.takesKeys = true; panel.makeKey() }
        guard let s = body["size"] as? [NSNumber], s.count == 2 else { return }
        resize(CGFloat(s[0].doubleValue), CGFloat(s[1].doubleValue))
        if let p = body["pill"] as? [NSNumber], p.count == 2 {   // only the pill drags; the card's own buttons take their clicks
            let w = CGFloat(p[0].doubleValue), h = CGFloat(p[1].doubleValue)
            handle?.frame = NSRect(x: (panel.frame.width - w) / 2, y: 0, width: w, height: h)
        }
    }
    // Grows around its bottom centre, so it stays under the eye.
    private func resize(_ w: CGFloat, _ h: CGFloat) {
        var f = panel.frame
        guard w > 0, h > 0, f.width != w || f.height != h else { return }
        f.origin.x = f.midX - w / 2; f.size = NSSize(width: w, height: h)
        panel.setFrame(clamp(f, to: panel.screen ?? mouseScreen), display: true)
    }

    // ---- Where it sits: remembered per display ----
    func displayKey(_ s: NSScreen) -> String { String(describing: s.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] ?? s.localizedName) }
    func clamp(_ f: NSRect, to s: NSScreen) -> NSRect {
        var r = f; let v = s.visibleFrame
        r.origin.x = min(max(v.minX, r.origin.x), v.maxX - r.width); r.origin.y = min(max(v.minY, r.origin.y), v.maxY - r.height)
        return r
    }
    func home(on s: NSScreen) -> NSPoint { NSPoint(x: s.visibleFrame.midX - panel.frame.width / 2, y: s.visibleFrame.minY + VoiceBar.margin) }
    func place(on s: NSScreen) {
        let saved = (Prefs.d["barFrames"] as? [String: [String: Double]])?[displayKey(s)]
        var f = panel.frame
        f.origin = saved.flatMap { d in d["x"].flatMap { x in d["y"].map { NSPoint(x: s.frame.minX + x, y: s.frame.minY + $0) } } } ?? home(on: s)
        panel.setFrame(clamp(f, to: s), display: true)
    }
    func remember() {
        guard let s = panel.screen else { return }
        var all = Prefs.d["barFrames"] as? [String: [String: Double]] ?? [:]
        all[displayKey(s)] = ["x": Double(panel.frame.midX - panel.frame.width / 2 - s.frame.minX), "y": Double(panel.frame.minY - s.frame.minY)]
        Prefs.set("barFrames", all)
    }
    func reset() {
        let s = panel.screen ?? mouseScreen
        var all = Prefs.d["barFrames"] as? [String: [String: Double]] ?? [:]
        all[displayKey(s)] = nil; Prefs.set("barFrames", all)
        panel.setFrameOrigin(home(on: s))
    }

    func menu() -> NSMenu {
        let m = NSMenu()
        for (key, action) in [("menu.openHome", #selector(openHome)), (Prefs.bool("paused") ? "menu.resume" : "menu.pause", #selector(pause)), ("menu.settings", #selector(openSettings)), ("bar.menu.reset", #selector(resetPosition)), ("menu.quit", #selector(quit))] {
            let i = NSMenuItem(title: L(key), action: action, keyEquivalent: ""); i.target = self; m.addItem(i)
        }
        return m
    }
    @objc func openHome() { Chiron.home.openHome() }
    @objc func pause() { bar.pause() }
    @objc func openSettings() { Chiron.home.openSettings() }
    @objc func resetPosition() { reset() }
    @objc func quit() { NSApp.terminate(nil) }

    // ---- The card ----
    func card(_ kind: String, _ data: [String: Any]) {
        guard !(kind == "draft" && ["allow", "pick"].contains(cardKind)) else { return }   // a voice reply to a card keeps the card
        cardClose?.cancel(); cardClose = nil
        cardKind = kind; panel.takesKeys = true; call("card", [kind, data])
    }
    func closeCard() {
        cardClose?.cancel(); cardClose = nil
        guard cardOpen else { return }
        cardKind = ""; panel.takesKeys = false; call("closeCard", [])
        if panel.isKeyWindow { panel.resignKey() }
    }
    // An answer stays 20 s after it ends, or after it has been read aloud. Anything waiting on the person stays until answered.
    func answerEnded() {
        cardClose?.cancel(); cardClose = nil
        guard cardKind == "answer", app.voice?.isRunning != true else { return }
        let close = DispatchWorkItem { [weak self] in self?.closeCard() }
        cardClose = close; DispatchQueue.main.asyncAfter(deadline: .now() + 20, execute: close)
    }

    // ---- States ----
    func state(_ name: String, _ text: String = "", done: String = "", settleAfter: Double? = nil) {
        settle?.cancel(); settle = nil
        call("state", [name, text, done])
        guard let settleAfter else { return }
        let idle = DispatchWorkItem { [weak self] in self?.call("state", ["idle", ""]) }
        settle = idle; DispatchQueue.main.asyncAfter(deadline: .now() + settleAfter, execute: idle)
    }
    func idle() { state("idle") }

    // What ui.html is told, in bar terms. A short answer stays on the pill; a long one, or anything needing a reply, is a card.
    func mirror(_ call: String, _ arg: Any?) {
        let text = arg as? String ?? ""
        switch call {
        case "listen": lastStep = ""; if cardKind == "answer" || cardKind == "rewrite" || cardKind == "failed" { closeCard() }; state("listening")
        case "level": if let v = arg as? Double ?? (arg as? NSNumber)?.doubleValue { self.call("level", [v]) }
        case "words": self.call("words", [text])
        case "think", "finishing": state("thinking")
        case "dictated":
            let line = (arg as? [String: Any])?["text"] as? String ?? ""
            line.isEmpty ? state("done", settleAfter: 2) : state("message", line, settleAfter: 4)
        case "msg", "stopped", "notice":
            if call == "stopped", ["allow", "pick"].contains(cardKind) { closeCard() }
            if text.isEmpty { idle() } else if VoiceBar.long(text, 140) { card("answer", ["text": text]); idle(); answerEnded() } else { state("message", text, settleAfter: 4) }
        case "line":
            let tag = text.first, words = String(text.dropFirst(2))
            if tag == "✓" {   // silent replies stay readable: about 2.5 words a second, never under 8 s
                lastStep = ""
                if VoiceBar.long(words, 90) { card("answer", ["text": words]); answerEnded() }
                state("done", VoiceBar.long(words, 90) ? "" : words, settleAfter: max(8, Double(words.split(separator: " ").count) / 2.5))
            }
            else if tag == "…" { if VoiceBar.long(words, 90) { card("answer", ["text": words]) } }
            else if tag == "▸" { state("thinking", words, done: lastStep); lastStep = words }   // what it just did, above what it is doing
            else if tag == "·" { state("thinking", words, done: lastStep) }
        case "pick": card("pick", arg as? [String: Any] ?? [:])
        case "ask":
            let a = arg as? [Any] ?? []
            card("allow", ["q": a.first as? String ?? "", "cmd": a.count > 1 ? a[1] as? String ?? "" : "", "retry": a.count > 2 && (a[2] as? String ?? "") == "retry", "details": a.count > 3 ? a[3] as? String ?? "" : ""])
        case "rewrite":
            let a = arg as? [Any] ?? []
            card("rewrite", ["draft": a.first as? String ?? "", "mode": a.count > 1 ? a[1] as? String ?? "replace" : "replace", "editable": a.count > 2 ? a[2] as? Bool ?? false : false])
        case "draft": card("draft", ["text": text])
        case "compose": if arg as? Bool == true { card("draft", ["text": ""]) }
        case "workerFailed": card("failed", [:])
        case "respond", "reset", "replaced": closeCard()
        case "copied": state("done", settleAfter: 2)
        case "paused": if arg as? Bool != false { state("message", L("menu.paused"), settleAfter: 4) }
        case "learned": state("message", L("bar.learned", ["word": text]), settleAfter: 4)
        default: break
        }
    }
    static func long(_ s: String, _ limit: Int) -> Bool { s.count > limit || s.contains("\n") || s.contains("\u{2028}") }
}
let voiceBar = VoiceBar()

extension App {
    // chiron.py --speak: voice stays the one running reader, so the talk key's and Esc's shush() stop it like `say`.
    func speakCloud(_ words: String, lang: String, voice speaker: String?, fallback: [String] = []) {
        shush()
        guard let (p, input) = cloudProcess(lang, speaker, fallback) else { return }
        p.terminationHandler = { [weak self] p in DispatchQueue.main.async {
            guard let self, self.voice === p else { return }; self.voice = nil; voiceBar.idle(); voiceBar.answerEnded(); self.hide(after: 2)
        } }
        do { try p.run() } catch { return }
        voice = p; voiceBar.state("speaking")
        input.write(Data(words.utf8)); try? input.close()
    }
    func cloudProcess(_ lang: String, _ speaker: String?, _ fallback: [String]) -> (Process, FileHandle)? {
        let chosen = speaker ?? Prefs.str("ttsVoice." + lang), speed = Prefs.num("speakRate") > 0 ? Prefs.num("speakRate") : 0.85
        let say = String(decoding: (try? JSONSerialization.data(withJSONObject: fallback)) ?? Data("[]".utf8), as: UTF8.self)
        let p = py(["--speak", lang, chosen, String(speed)], ["CHIRON_SAY_ARGS": say]), input = Pipe()
        p.standardInput = input
        return (p, input.fileHandleForWriting)
    }
    // A lesson caption: the same cached cloud voice; nil is silence, and the caption is on screen anyway.
    func speakCaption(_ words: String) -> Process? {
        let apple = Prefs.bool("appleVoice")
        if Keychain.has("google"), let (p, input) = cloudProcess(Strings.lang, nil, apple ? sayRate() : []) {
            do { try p.run() } catch { return nil }
            input.write(Data(words.utf8)); try? input.close(); return p
        }
        guard apple else { return nil }
        let p = Process(); p.executableURL = URL(fileURLWithPath: "/usr/bin/say"); p.arguments = readAloudArguments(words, rate: sayRate()) {}
        try? p.run(); return p
    }

    func cardClosed() { pinned = false; if !busy { gone() } }
    func closeOpenCard() { if voiceBar.cardOpen { voiceBar.closeCard(); cardClosed() } }

    // Test my voice: five seconds through the normal listening path in the chosen language, ending before anything is asked.
    func testVoice(_ lang: String, _ done: @escaping (String) -> Void) {
        guard !engine.isRunning, !busy, voiceTest == nil else { return done("") }
        voiceTestLang = lang; voiceTest = done
        start()
        guard engine.isRunning else { return endVoiceTest("") }
        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { [weak self] in if self?.voiceTest != nil { self?.stop() } }
        DispatchQueue.main.asyncAfter(deadline: .now() + 9) { [weak self] in self?.endVoiceTest(self?.text ?? "") }   // finalizing hung
    }
    func endVoiceTest(_ heard: String) {
        guard let done = voiceTest else { return }
        voiceTest = nil; voiceTestLang = nil; done(heard)
        hush(); js("msg", ""); hide(after: 0.2)
    }
    // Said "type …" while talking: on from here it is a dictation, into the app the user is in.
    func routeToDictation(_ words: String) {
        aheadItem?.cancel(); dropAhead(); unwarm()
        dictateCleanup = Prefs.str("dictateMode") == "cleanup"; dictateFellBack = false; dictateTimedOut = false
        captureDictationSelection(); replacement = nil
        if dictateCleanup { warmDictationCleanup() }
        dictateSeconds = Date().timeIntervalSince(began); dictateReleased = Date()
        dictating = true; text = words
        js("finishing", dictateCleanup ? "Cleaning up…" : "")
        finishDictation()
    }
}

// Settings speed (0.7–1.1) as `say -r`; macOS speaks about 190 words a minute at 1.0.
func sayRate(_ speed: Double? = nil) -> [String] { ["-r", String(Int((max(0.7, min(1.1, speed ?? (Prefs.num("speakRate") > 0 ? Prefs.num("speakRate") : 0.85))) * 190).rounded()))] }
// "type hello" or "लिखो नमस्ते" while talking: the words after it go where the user is typing, not to Chiron.
func dictationRequest(_ said: String) -> String? {
    let re = try! NSRegularExpression(pattern: "^\\s*(?:type|likho|likhiye|लिखो|लिखिए|लिखिये|टाइप करो|टाइप)(?![\\p{L}\\p{M}\\p{N}])[\\s,:;.-]*", options: .caseInsensitive)
    let ns = said as NSString
    guard let m = re.firstMatch(in: said, range: NSRange(location: 0, length: ns.length)) else { return nil }
    let rest = ns.substring(from: m.range.length).trimmingCharacters(in: .whitespacesAndNewlines)
    return rest.isEmpty ? nil : rest
}
