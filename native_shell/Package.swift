// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "IRISNativeShell",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "IRISNative", targets: ["IRISNative"]),
    ],
    targets: [
        .executableTarget(
            name: "IRISNative",
            path: "Sources/IRISNative"
        ),
    ]
)
