"""sutlac.jpeg -> sutlac.png + sutlac-face.png (arka plan şeffaf). Tek seferlik araç.
Fotoğrafı değiştirirsen bunu tekrar çalıştır."""
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

P = "/Users/firatozgurozcan/Desktop/poopy/"
im = Image.open(P + "sutlac.jpeg").convert("RGB")
a = np.asarray(im).astype(np.int16)
lo, hi = a.min(2), a.max(2)

# stüdyo fonu: parlak ve nötr. kedinin kremi sıcak, kanal farkı yüksek.
bg_like = (lo > 196) & ((hi - lo) < 14)
lab, _ = ndimage.label(bg_like)
edge = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
edge.discard(0)
bg = np.isin(lab, list(edge))
cat = ndimage.binary_closing(ndimage.binary_fill_holes(~bg), np.ones((5, 5)))

alpha = np.asarray(Image.fromarray((cat * 255).astype(np.uint8))
                   .filter(ImageFilter.GaussianBlur(1.0))).astype(np.float64)
# antialias yalnızca sınırda kalsın. border_value=1: görüntü kenarı da "fon içi"
# sayılsın, yoksa ilk iki satır korumadan kaçıp puslu bir dikdörtgen bırakıyor.
alpha[ndimage.binary_erosion(~cat, np.ones((5, 5)), border_value=1)] = 0
alpha = np.clip((alpha - 70) * (255 / 150), 0, 255).astype(np.uint8)

out = im.copy(); out.putalpha(Image.fromarray(alpha))
out = out.crop(out.getbbox())
out.thumbnail((760, 760), Image.LANCZOS)
out.save(P + "sutlac.png", optimize=True)

w, h = out.size
out.crop((int(w*.08), 0, int(w*.92), int(w*.84))).resize((180, 180), Image.LANCZOS) \
   .save(P + "sutlac-face.png", optimize=True)

al = np.asarray(out)[..., 3]
print("boyut:", out.size, "| tam opak %:", round(100*(al == 255).mean(), 1),
      "| üst şerit ort:", round(al[:5].mean(), 2),
      "| köşeler:", al[0,0], al[0,-1], al[-1,-1])

# --- favicon: kafayı tespit edip daireye ortala ---
al = np.asarray(out)[..., 3] > 128
Hh, Ww = al.shape
ext = np.zeros(Hh, int)
for r in range(Hh):
    cc = np.where(al[r])[0]
    if len(cc):
        ext[r] = cc.max() - cc.min()
_lo, _hi = int(Hh * .35), int(Hh * .58)
neck = _lo + int(np.argmin(ext[_lo:_hi]))      # yanaklardan sonraki daralma = boyun
# neck = çenenin daraldığı yer; asıl çene ucu bunun biraz altında kalıyor.
# burun ve ağzı kesmemek için oraya kadar in.
chin = min(Hh, int(neck * 1.17))
cols = np.where(al[:chin].any(0))[0]
head = out.crop((int(cols.min()), 0, int(cols.max()) + 1, chin))

# çene hizasındaki düz kesik zemine karışsın
ha = np.asarray(head).astype(np.float64).copy()
_k = int(ha.shape[0] * .92)
ha[_k:, :, 3] *= np.clip(np.linspace(1, 0, ha.shape[0] - _k), 0, 1)[:, None]
head = Image.fromarray(ha.astype(np.uint8))

# zeminsiz, çerçevesiz: sadece kafa. şeffaf kare tuvale ortalanır.
S = 512
scale = S * .94 / max(head.width, head.height)
hw, hh = int(head.width * scale), int(head.height * scale)
ico = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ico.alpha_composite(head.resize((hw, hh), Image.LANCZOS), ((S - hw) // 2, (S - hh) // 2))
ico.save(P + "favicon.png", optimize=True)
ico.resize((64, 64), Image.LANCZOS).save(P + "favicon-64.png", optimize=True)
print("favicon:", ico.size, "| boyun:", neck, "| çene:", chin, "| kafa:", head.size)
