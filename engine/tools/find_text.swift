// find_text.swift: find a phrase in a (tall) screenshot with the Mac's own Vision OCR and print its box per line.
// Usage: find_text <image> <y0> <y1> "<phrase>"
// Prints JSON: [[x, y, w, h], ...] in the image's pixel coordinates (one box per text line the phrase sits on).
import Foundation
import Vision
import CoreImage

let a = CommandLine.arguments
guard a.count >= 5, let y0 = Double(a[2]), let y1 = Double(a[3]) else { print("usage: find_text <image> <y0> <y1> <phrase>"); exit(1) }
let phrase = a[4].lowercased()
guard let full = CIImage(contentsOf: URL(fileURLWithPath: a[1])) else { print("[]"); exit(0) }
let H = full.extent.height, W = full.extent.width
// CIImage origin is bottom-left: crop rows y0..y1 counted from the top
let crop = full.cropped(to: CGRect(x: 0, y: H - y1, width: W, height: y1 - y0))
let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate; req.usesLanguageCorrection = true
try VNImageRequestHandler(ciImage: crop, options: [:]).perform([req])
var out: [[Int]] = []
let ch = y1 - y0
for obs in req.results ?? [] {
  guard let cand = obs.topCandidates(1).first else { continue }
  let s = cand.string.lowercased()
  // match the phrase, or the part of it that sits on this line (phrases can wrap)
  let words = phrase.split(separator: " ").map(String.init)
  var best: Range<String.Index>? = nil
  for n in stride(from: words.count, through: 1, by: -1) {
    for st in 0...(words.count - n) {
      let sub = words[st..<(st + n)].joined(separator: " ")
      if let r = s.range(of: sub), n >= 1, (n == words.count || sub.count >= 6) { best = r; break }
    }
    if best != nil { break }
  }
  guard let r = best, let box = try? cand.boundingBox(for: r) else { continue }
  let bb = box.boundingBox  // normalized, origin bottom-left, relative to the crop
  let x = Int(bb.minX * W), w = Int(bb.width * W), h = Int(bb.height * ch)
  let y = Int(y0 + (1 - bb.maxY) * ch)
  out.append([x, y, w, h])
}
let data = try JSONSerialization.data(withJSONObject: out)
print(String(data: data, encoding: .utf8)!)
