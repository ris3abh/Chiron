// Native labels (menu bar, callouts, permission help) in the app language, from the same ui/strings/<lang>.json the page uses.
import Foundation

enum Strings {
    static var cache: [String: [String: String]] = [:]
    static var lang: String { ["en", "hi"].contains(Prefs.str("lang")) ? Prefs.str("lang") : "en" }
    static func table(_ code: String) -> [String: String] {
        if let t = cache[code] { return t }
        let url = URL(fileURLWithPath: dir + "/ui/strings/\(code).json")
        let raw = (try? JSONSerialization.jsonObject(with: Data(contentsOf: url))) as? [String: Any] ?? [:]
        let t = raw.compactMapValues { $0 as? String }
        cache[code] = t
        return t
    }
    // Every string the page will ever need, for when the page can't fetch strings/*.json itself.
    static func all(_ code: String) -> [String: String] { table(code) }
}

// L("menu.settings") or L("menu.hint.hold", ["keys": "⌃⌥Space"]): falls back to English, then the key itself.
func L(_ key: String, _ values: [String: String] = [:]) -> String {
    var text = Strings.table(Strings.lang)[key] ?? Strings.table("en")[key] ?? key
    for (k, v) in values { text = text.replacingOccurrences(of: "{\(k)}", with: v) }
    return text
}
