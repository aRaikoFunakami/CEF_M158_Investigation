// svg2png.swift <in.svg> <out.png> [倍率]: SVG を指定倍率の PNG にする(記事の図用)。macOS の NSImage の SVG 描画を使う。
import AppKit
let a = CommandLine.arguments
let scale = a.count > 3 ? Double(a[3])! : 2.0
guard let img = NSImage(contentsOf: URL(fileURLWithPath: a[1])) else { fatalError("読めない: \(a[1])") }
let w = Int(img.size.width * scale), h = Int(img.size.height * scale)
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSColor.white.setFill(); NSRect(x: 0, y: 0, width: w, height: h).fill()
img.draw(in: NSRect(x: 0, y: 0, width: w, height: h))
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[2]))
print("\(a[2]) \(w)x\(h)")
