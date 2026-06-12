// swift-tools-version: 5.9
import PackageDescription

// DO NOT MODIFY THIS FILE - managed by Capacitor CLI commands
let package = Package(
    name: "CapApp-SPM",
    platforms: [.iOS(.v15)],
    products: [
        .library(
            name: "CapApp-SPM",
            targets: ["CapApp-SPM"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", exact: "8.3.1"),
        .package(name: "CapacitorApp", path: "../../../../node_modules/.pnpm/@capacitor+app@8.1.0_@capacitor+core@8.3.1/node_modules/@capacitor/app"),
        .package(name: "CapacitorBrowser", path: "../../../../node_modules/.pnpm/@capacitor+browser@8.0.3_@capacitor+core@8.3.1/node_modules/@capacitor/browser"),
        .package(name: "CapacitorHaptics", path: "../../../../node_modules/.pnpm/@capacitor+haptics@8.0.2_@capacitor+core@8.3.1/node_modules/@capacitor/haptics"),
        .package(name: "CapacitorKeyboard", path: "../../../../node_modules/.pnpm/@capacitor+keyboard@8.0.3_@capacitor+core@8.3.1/node_modules/@capacitor/keyboard"),
        .package(name: "CapacitorSplashScreen", path: "../../../../node_modules/.pnpm/@capacitor+splash-screen@8.0.1_@capacitor+core@8.3.1/node_modules/@capacitor/splash-screen"),
        .package(name: "CapgoCapacitorUpdater", path: "../../../../node_modules/.pnpm/@capgo+capacitor-updater@8.49.0_@capacitor+core@8.3.1/node_modules/@capgo/capacitor-updater")
    ],
    targets: [
        .target(
            name: "CapApp-SPM",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm"),
                .product(name: "CapacitorApp", package: "CapacitorApp"),
                .product(name: "CapacitorBrowser", package: "CapacitorBrowser"),
                .product(name: "CapacitorHaptics", package: "CapacitorHaptics"),
                .product(name: "CapacitorKeyboard", package: "CapacitorKeyboard"),
                .product(name: "CapacitorSplashScreen", package: "CapacitorSplashScreen"),
                .product(name: "CapgoCapacitorUpdater", package: "CapgoCapacitorUpdater")
            ]
        )
    ]
)
