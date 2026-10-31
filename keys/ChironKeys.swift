// The only program that touches Chiron's Keychain items. macOS ties Keychain permission to the exact binary when an app has no
// Apple Team ID, so a key held by Chiron itself asked for the password again after every build. This stays byte-for-byte the same
// across builds (build.sh reuses one signed copy until this file changes), so "Always Allow" is answered once. Keep it small and leave it alone.
// ChironKeys [--secret] get|set|delete <name>: set reads the value from stdin so it never shows in `ps`.
import Foundation
import Security

let service = "com.chiron.app", names = ["anthropic", "openai", "jev", "custom", "google"]
func query(_ name: String) -> [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: name] }
var args = Array(CommandLine.arguments.dropFirst())
if args.first == "--secret" { args.removeFirst() }
guard args.count == 2, names.contains(args[1]) else {
    FileHandle.standardError.write(Data("usage: ChironKeys get|set|delete <\(names.joined(separator: "|"))>\n".utf8)); exit(2)
}
let name = args[1]
switch args[0] {
case "get":
    var q = query(name), out: CFTypeRef?
    q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
    guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data, let value = String(data: data, encoding: .utf8) else { exit(1) }
    print(value)
case "set":
    let value = String(decoding: FileHandle.standardInput.readDataToEndOfFile(), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    guard !value.isEmpty, let data = value.data(using: .utf8) else { exit(1) }
    let found = SecItemUpdate(query(name) as CFDictionary, [kSecValueData as String: data] as CFDictionary)
    if found == errSecSuccess { exit(0) }
    guard found == errSecItemNotFound else { exit(1) }
    var q = query(name); q[kSecValueData as String] = data
    q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly   // never synced to iCloud or restored to another Mac
    q[kSecAttrLabel as String] = "Chiron: \(name)"
    exit(SecItemAdd(q as CFDictionary, nil) == errSecSuccess ? 0 : 1)
case "delete":
    let s = SecItemDelete(query(name) as CFDictionary)
    exit(s == errSecSuccess || s == errSecItemNotFound ? 0 : 1)
default: exit(2)
}
