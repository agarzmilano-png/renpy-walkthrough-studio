# v0.1.0b1 — GitHub beta

İlk GitHub beta sürümü. Arayüz ve üretilen ipuçları ağırlıklı Türkçedir.

## İndirme

- **Windows x64:** `RenpyWalkthroughStudio-0.1.0b1-windows-x64.zip` dosyasını
  tamamen çıkarın. EXE ile `_internal` klasörünü birlikte tutun. Python gerekmez.
- **Kaynak:** GitHub kaynak arşivi veya `renpy-walkthrough-studio-0.1.0b1-source.zip`.
  Python 3.12+; GUI için `requirements-gui.txt` bağımlılıklarını kurun.
- ZIP özetlerini `SHA256SUMS.txt` ile karşılaştırın:
  `Get-FileHash .\RenpyWalkthroughStudio-0.1.0b1-windows-x64.zip -Algorithm SHA256`

## Önemli

Önce oyunun ayrı kopyasını alın; orijinale uygulamayın. Yedekleme açık kalsın.
Nötr karar “doğrulanmamış” olabilir. Bu sürüm her oyunda bütün rotaları ve her
Python/Ren'Py davranışını garanti etmez. Rehber/LLM veya API anahtarı gerekmez.
CLI desteği için konsol korunur; GUI arkasında konsol penceresi görülebilir.

Paket imzasızdır. Sistem güvenlik korumasını kapatmayın. Temiz Windows VM testi
ve kod imzalama, yerel EXE kontrollerinden ayrı yayın kontrolleridir.

## Değişiklikler ve doğrulama

- Bağlamsal giriş durumu, gerçek çağıran ve ilgili değişkenler üzerinden analiz.
- Bilinmeyen etkiler/kapsam eksikliği kesin renge dönüştürülmez.
- Desteklenen kaynak yapılarda Both/All sahne birleştirme.
- Salt okunur tarama, değişen kaynak kontrolü ve otomatik yedekler.
- MIT proje lisansı; gömülü bileşen ve runtime bildirimleri ayrıca korunur.

Test kapsamı ve güncel sonuçlar: `docs/VALIDATION.md` ve
`docs/validation-0.1.0b1.json`. GitHub Actions'ın hazırlanmış olması CI'ın
sunucuda başarıyla çalıştığı anlamına gelmez.
