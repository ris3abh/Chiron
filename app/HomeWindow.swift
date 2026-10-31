// The one page (ui/home.html) in one window: a sidebar (Home, Insights, Dictionary) and Settings as a sheet inside it.
// The Dock icon shows only while it is open, so Chiron stays a menu bar app the rest of the time.
import Cocoa
import WebKit

final class HomeWindows: NSObject, NSWindowDelegate {
    var home: NSWindow?
    var homeWeb: WKWebView?
    let bridge = HomeBridge()
    var timer: Timer?

    var webs: [WKWebView] { [homeWeb].compactMap { $0 } }
    var visible: Bool { home?.isVisible == true }

    func openHome() { show(settings: false) }
    // Menu bar Settings… opens the same window with its Settings sheet up.
    func openSettings() { show(settings: true) }

    private func show(settings: Bool) {
        if let w = home {
            NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true); w.makeKeyAndOrderFront(nil)
            if settings { push("settings", [String: Any]()) }
            return
        }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1180, height: 780), styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.title = "Chiron"   // still read by VoiceOver and the Window menu
        w.titlebarAppearsTransparent = true; w.titleVisibility = .hidden
        w.minSize = NSSize(width: 760, height: 560)
        w.isReleasedWhenClosed = false; w.delegate = self
        w.setFrameAutosaveName("ChironMain")   // remembers where the user left it; a new name so the old, smaller Home size doesn't carry over
        if !w.setFrameUsingName(w.frameAutosaveName) { w.center() }
        applySharing(w)
        let root = NSView(frame: w.contentRect(forFrameRect: w.frame))
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(bridge, name: "home")
        // .native tells the page it fills a window whose title bar is transparent (keep clear of the traffic lights).
        cfg.userContentController.addUserScript(WKUserScript(source: "document.documentElement.classList.add('native')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let web = WKWebView(frame: root.bounds, configuration: cfg)
        web.autoresizingMask = [.width, .height]
        web.setValue(false, forKey: "drawsBackground")   // no white flash before the page paints its own colour
        web.underPageBackgroundColor = .clear
        bridge.attach(web)
        HomeWindows.load(web, settings: settings)
        root.addSubview(web)
        root.addSubview(DragStrip(in: root.bounds))
        w.contentView = root
        home = w; homeWeb = web
        applyTheme()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true); w.makeKeyAndOrderFront(nil)
        startTimer()
    }

    // The page's theme also sets the window's, so the traffic lights and scroll bars match it.
    func applyTheme() {
        switch Prefs.str("theme") {
        case "light": home?.appearance = NSAppearance(named: .aqua)
        case "dark": home?.appearance = NSAppearance(named: .darkAqua)
        default: home?.appearance = nil
        }
    }

    // A file URL with read access to ui/, so strings/*.json and fonts/*.woff2 load as relative files.
    // The page's own CSP keeps it off the network.
    static func load(_ web: WKWebView, settings: Bool) {
        let ui = URL(fileURLWithPath: dir + "/ui", isDirectory: true)
        var page = URLComponents(url: ui.appendingPathComponent("home.html"), resolvingAgainstBaseURL: false)!
        if settings { page.fragment = "settings" }
        web.loadFileURL(page.url ?? ui.appendingPathComponent("home.html"), allowingReadAccessTo: ui)
    }

    // Fresh state every 5 s while the window shows it, and right after every ask (App calls refresh()).
    func startTimer() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let self, self.visible else { return }
            self.refresh()
        }
    }
    func refresh() {
        guard !webs.isEmpty else { return }
        bridge.homeState { [weak self] state in self?.push("state", state) }
    }
    func push(_ event: String, _ data: Any) { webs.forEach { callJS($0, "bridge.push", [event, data]) } }

    func windowWillClose(_ n: Notification) {
        guard let w = n.object as? NSWindow, w === home else { return }
        homeWeb?.configuration.userContentController.removeScriptMessageHandler(forName: "home")
        bridge.detach(homeWeb)
        home = nil; homeWeb = nil
        timer?.invalidate(); timer = nil
        NSApp.setActivationPolicy(.accessory)   // back to a menu bar app: no Dock icon
    }
}

// The web view covers the transparent title bar, so it would swallow drags there. This strip lies over the
// page's 52 pt title strip, left of its theme and language buttons, and moves the window like a title bar.
final class DragStrip: NSView {
    static let height: CGFloat = 52, rightControls: CGFloat = 230
    convenience init(in bounds: NSRect) {
        self.init(frame: NSRect(x: 0, y: bounds.height - DragStrip.height, width: max(0, bounds.width - DragStrip.rightControls), height: DragStrip.height))
        autoresizingMask = [.width, .minYMargin]
    }
    override func mouseDown(with event: NSEvent) {
        if event.clickCount == 2 { window?.performZoom(nil) } else { window?.performDrag(with: event) }
    }
}
