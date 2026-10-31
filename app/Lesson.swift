// Runs a lesson: one skill card, one step at a time, on ScreenDrawing's marks and click detection. The person does every click;
// Chiron only draws, checks with chiron.py --lesson check, hints, and offers to do a step after three hints.
import Cocoa

final class Lesson {
    static var current: Lesson?
    let card: [String: Any], steps: [[String: Any]], id: String, planned: Double, started = Date()
    var index = 0, hints = 0, results: [[String: Any]] = [], stepStart = Date(), checks = 0, generation = 0
    var awaiting: ((Bool) -> Void)?   // a Yes/No or Allow card is up; its answer lands here

    static func start(_ json: Data) {
        guard let p = try? JSONSerialization.jsonObject(with: json) as? [String: Any], let card = p["card"] as? [String: Any], let steps = card["steps"] as? [[String: Any]], !steps.isEmpty else { return }
        current?.end(finished: false)
        let lesson = Lesson(card, steps, p["id"] as? String ?? "", (p["usd"] as? NSNumber)?.doubleValue ?? 0)
        current = lesson; lesson.show()
    }
    init(_ card: [String: Any], _ steps: [[String: Any]], _ id: String, _ planned: Double) { self.card = card; self.steps = steps; self.id = id; self.planned = planned }

    var step: [String: Any] { steps[index] }
    // Read at every step, so switching EN ↔ हिं mid-lesson changes the next caption with no AI call.
    var caption: String { let say = step["say"] as? [String: String] ?? [:]; return say[Strings.lang] ?? say["en"] ?? "" }
    func paintBar() { voiceBar.state("teaching", L("bar.lesson", ["n": String(index + 1), "total": String(steps.count)])) }
    func python(_ what: String, _ extra: [String: Any] = [:], env: [String: String] = [:], _ done: @escaping ([String: Any]) -> Void) {
        HomeBridge.python(["--lesson", what], ["step": step].merging(extra) { $1 }, env: env) { done($0 ?? [:]) }
    }

    func show() {
        generation += 1; hints = 0; checks = 0; stepStart = Date(); awaiting = nil
        paintBar(); draw()
    }
    func draw() {
        let drawing = app.drawing, target = step["target"] as? [String: Any] ?? [:], gen = generation
        drawing.lessonStep = (index + 1, steps.count); drawing.onHit = { [weak self] in self?.clickedTarget() }; drawing.onMiss = { [weak self] _ in self?.clickedElsewhere() }
        drawing.onLessonStop = { [weak self] in self?.end(finished: false) }; drawing.onLessonBack = { [weak self] in self?.back() }
        drawing.onLessonNext = { [weak self] in self?.complete("skipped") }; drawing.onShowMe = { [weak self] in self?.showMe() }
        if let frame = Lesson.locate(target), let data = Lesson.request(caption, frame), drawing.receive(data) { voiceBar.closeCard(); return }
        // No such control on screen (a video, a page still loading): the words on the card, and the window itself tells when it's done.
        drawing.clearLesson(); voiceBar.card("answer", ["text": caption]); app.voice = app.speakCaption(caption)
        watch(gen)
    }
    func watch(_ gen: Int) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 6) { [weak self] in
            guard let self, gen == generation, Lesson.current === self, awaiting == nil, checks < 10 else { return }
            checks += 1
            python("check") { [weak self] r in
                guard let self, gen == generation else { return }
                if r["result"] as? String == "correct" { complete("correct") } else { watch(gen) }
            }
        }
    }
    func clickedTarget() { check(afterClick: true) }
    func clickedElsewhere() { DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in self?.check(afterClick: false) } }
    func check(afterClick: Bool) {
        let gen = generation
        python("check") { [weak self] r in
            guard let self, gen == generation, awaiting == nil else { return }
            switch r["result"] as? String ?? "unsure" {
            case "correct": complete("correct")
            case "loading": DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in if self?.generation == gen { self?.check(afterClick: afterClick) } }
            case "wrong": hint(r["fault"] as? String ?? "")
            default:
                guard afterClick else { return }   // a stray click with no clear answer needs no reaction
                ask(L("lesson.didItWork")) { [weak self] yes in if yes { self?.complete("correct") } else { self?.hint("nothing_happened") } }
            }
        }
    }
    func hint(_ fault: String) {
        hints += 1
        guard hints < 3 else { return offerToDo() }
        python("hint", ["fault": fault]) { [weak self] r in
            guard let self else { return }
            let words = r["text"] as? String ?? ""
            voiceBar.state("teaching", words); app.voice = app.speakCaption(words)
            draw()   // the arrow goes back on the right target
        }
    }
    func showMe() { hints += 1; if hints >= 3 { offerToDo() } else { draw() } }
    func ask(_ question: String, _ done: @escaping (Bool) -> Void) {
        awaiting = done
        voiceBar.card("choice", ["q": question, "yes": L("lesson.yes"), "no": L("lesson.no")])
    }
    func answer(_ yes: Bool) { let done = awaiting; awaiting = nil; voiceBar.closeCard(); done?(yes) }
    // Doing a step is a Hands click outside the person's own: a risky one needs the same Allow card as anything else.
    func offerToDo() {
        ask(L("lesson.doIt")) { [weak self] yes in
            guard let self else { return }
            guard yes else { return draw() }
            python("risky") { [weak self] r in
                guard let self else { return }
                let question = r["q"] as? String ?? "", label = (step["target"] as? [String: Any])?["label"] as? String ?? ""
                guard !question.isEmpty else { return click(label, allowed: false) }
                awaiting = { [weak self] ok in if ok { self?.click(label, allowed: true) } else { self?.draw() } }
                voiceBar.card("allow", ["q": question, "cmd": label, "retry": false, "details": ""])
            }
        }
    }
    func click(_ label: String, allowed: Bool) {
        HomeBridge.python(["--lesson", "do"], ["label": label], env: allowed ? ["CHIRON_ALLOWED_CLICK": label] : [:]) { [weak self] r in
            guard let self else { return }
            if r?["ok"] as? Bool == true { complete("chiron-did") } else { draw() }
        }
    }
    func complete(_ result: String) {
        generation += 1
        results.append(["id": step["id"] ?? "", "result": result, "hints": hints, "secs": Int(Date().timeIntervalSince(stepStart)), "say": caption])
        guard index + 1 < steps.count else { return end(finished: true) }
        voiceBar.state("teaching", L("lesson.praise"))
        app.drawing.clearLesson()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { [weak self] in
            guard let self, Lesson.current === self else { return }
            index += 1; show()
        }
    }
    func back() { guard index > 0 else { return }; index -= 1; results.removeLast(min(1, results.count)); show() }
    // Said while a lesson runs; false lets it through as an ordinary ask.
    func heard(_ said: String) -> Bool {
        let words = transcriptKey(said)
        if awaiting != nil {
            if ["yes", "haan", "ha", "हाँ", "हां", "ok"].contains(words) { answer(true); return true }
            if ["no", "nahi", "nahin", "नहीं"].contains(words) { answer(false); return true }
        }
        if ["next", "aage", "agla", "आगे", "अगला"].contains(words) { complete("skipped"); return true }
        if ["back", "peeche", "piche", "पीछे"].contains(words) { back(); return true }
        if ["show me", "dikhao", "dikhaiye", "दिखाओ", "दिखाइए"].contains(words) { showMe(); return true }
        if ["stop", "ruko", "roko", "bas", "रुको", "रोको", "बस"].contains(words) { end(finished: false); return true }
        return false
    }
    func end(finished: Bool) {
        guard Lesson.current === self else { return }
        Lesson.current = nil; generation += 1; awaiting = nil
        app.drawing.clearLesson(); voiceBar.closeCard()
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        let row: [String: Any] = ["card": card, "steps": results, "finished": finished, "usd": planned, "id": id, "at": f.string(from: started)]
        HomeBridge.python(["--lesson", "end"], row) { _ in home.refresh() }
        voiceBar.state(finished ? "done" : "message", finished ? L("lesson.praise") : "", settleAfter: 4)
    }

    // ---- The screen ----
    // Where a target is, by the Accessibility tree of its app. Quartz points, as the drawing uses.
    static func locate(_ target: [String: Any]) -> CGRect? {
        guard let name = target["app"] as? String, let label = (target["label"] as? String)?.lowercased(), !label.isEmpty else { return nil }
        let named = NSWorkspace.shared.runningApplications.first { $0.localizedName == name || (name == "Dock" && $0.bundleIdentifier == "com.apple.dock") }
        // Then the front app: the Apple and app menus belong to whichever app is in front, whatever a plan calls it.
        for a in [named, NSWorkspace.shared.frontmostApplication].compactMap({ $0 }) {
            if let frame = find(label, role: target["role"] as? String ?? "", in: a) { return frame }
        }
        return nil
    }
    static func find(_ label: String, role: String, in a: NSRunningApplication) -> CGRect? {
        var queue = [AXUIElementCreateApplication(a.processIdentifier)], looked = 0
        var best: (CGRect, Int)?
        while !queue.isEmpty, looked < 4000 {
            let e = queue.removeFirst(); looked += 1
            let found = Hands.name(e).lowercased()
            if !found.isEmpty, found == label || found.contains(label) {
                let frame = Hands.frame(e), same = (Hands.attribute(e, kAXRoleAttribute) as? String) == role
                let rank = (found == label ? 2 : 0) + (same ? 1 : 0)
                if frame.width > 2, frame.height > 2, rank > (best?.1 ?? -1) { best = (frame, rank) }
                if rank == 3 { break }
            }
            queue += Hands.children(e)
        }
        return best?.0
    }
    // One step as a DrawingRequest: an amber ring on the target, waiting for a click inside it. ScreenDrawing can only tell a real window
    // from the id, so a lesson says so with onHit and these placeholders are never checked.
    static func request(_ caption: String, _ f: CGRect) -> Data? {
        let box = [f.minX - 6, f.minY - 6, f.width + 12, f.height + 12].map { Double($0) }
        let step: [String: Any] = ["id": "lesson", "say": caption, "shapes": [["kind": "rect", "rect": box, "color": "yellow"]], "wait": true, "hit": box, "timeout": 120]
        let screen = NSScreen.screens.first?.frame ?? .zero
        return try? JSONSerialization.data(withJSONObject: ["steps": [step], "teaching": false, "state": "",
            "target": ["pid": Int(ProcessInfo.processInfo.processIdentifier), "windowID": "1", "windowFrame": [0, 0, Double(screen.width), Double(screen.height)]]])
    }
}

// The lesson's card: larger words, a step count, and Back, Show me, Next and Stop.
final class LessonCalloutView: NSView {
    var back: (() -> Void)?, next: (() -> Void)?, stop: (() -> Void)?, showMe: (() -> Void)?
    static let width: CGFloat = 340
    static func font() -> NSFont { .systemFont(ofSize: Prefs.str("captionSize") == "l" ? 26 : 20, weight: .medium) }
    static func textHeight(_ text: String) -> CGFloat {
        ceil((text as NSString).boundingRect(with: CGSize(width: width - 40, height: .greatestFiniteMagnitude), options: [.usesLineFragmentOrigin, .usesFontLeading], attributes: [.font: font()]).height) + 4
    }
    static func size(_ text: String) -> CGSize { CGSize(width: width, height: 16 + 20 + 8 + textHeight(text) + 14 + 44 + 16) }
    override var isFlipped: Bool { true }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    init(frame: CGRect, card: CGRect, side: NSRectEdge?, tip: CGFloat, text: String, step: Int, total: Int) {
        super.init(frame: frame)
        wantsLayer = true
        let shape = CAShapeLayer(), path = DrawingCalloutView.bubble(card, side: side, tip: tip)
        shape.path = path; shape.fillColor = NSColor(calibratedRed: 0.13, green: 0.12, blue: 0.11, alpha: 0.97).cgColor
        shape.strokeColor = NSColor(calibratedRed: 0.96, green: 0.71, blue: 0.25, alpha: 0.75).cgColor; shape.lineWidth = 1.5
        shape.shadowColor = NSColor.black.cgColor; shape.shadowOpacity = 0.35; shape.shadowRadius = 10; shape.shadowOffset = .zero; shape.shadowPath = path
        layer?.addSublayer(shape)
        setAccessibilityElement(true); setAccessibilityRole(.group); setAccessibilityLabel(L("lesson.step", ["n": String(step), "total": String(total)]))
        let count = NSTextField(labelWithString: L("lesson.step", ["n": String(step), "total": String(total)]))
        count.font = .systemFont(ofSize: 15, weight: .semibold); count.textColor = NSColor(calibratedRed: 0.97, green: 0.75, blue: 0.39, alpha: 1)
        count.frame = CGRect(x: card.minX + 20, y: card.minY + 16, width: card.width - 40, height: 20); addSubview(count)
        let words = NSTextField(wrappingLabelWithString: text); words.font = Self.font(); words.textColor = .white; words.isSelectable = false
        words.frame = CGRect(x: card.minX + 20, y: count.frame.maxY + 8, width: card.width - 40, height: Self.textHeight(text)); addSubview(words)
        var x = card.minX + 20
        let y = words.frame.maxY + 14
        for (title, action, wide) in [(L("lesson.back"), #selector(goBack), false), (L("lesson.showMe"), #selector(again), true), (L("lesson.next"), #selector(goNext), false), (L("lesson.stop"), #selector(end), false)] {
            let b = NSButton(title: title, target: self, action: action); b.bezelStyle = .rounded; b.controlSize = .large
            b.frame = CGRect(x: x, y: y, width: wide ? 92 : 68, height: 40); x += b.frame.width + 6; addSubview(b)
        }
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    @objc func goBack() { back?() }
    @objc func goNext() { next?() }
    @objc func again() { showMe?() }
    @objc func end() { stop?() }
}
