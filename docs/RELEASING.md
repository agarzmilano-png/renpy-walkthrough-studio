# GitHub yayınlama kontrol listesi

## 1. Doğru klasör

GitHub'a yalnız bu temiz depo klasörünü yükleyin. Geliştirme çalışma alanını,
oyunları, SDK'ları, test motoru kopyalarını veya geçici raporları yüklemeyin.
Yayımdan önce:

```powershell
python -B -m unittest discover -s tests
python scripts/check_repository.py
git status --short
```

Bu hazırlık GitHub'a otomatik push yapmaz ve sizin adınıza depo oluşturmaz.
Depoyu GitHub'da kendi hesabınızdan oluşturun. Temiz klasörü git ile bağladıktan
sonra yalnız inceleyip onayladığınız dosyaları commit/push edin. MIT lisansı
seçilmiştir; kullanıcı adınızı telif sahibi olarak göstermek isterseniz orijinal
katkı sahipliğinizle uyumlu biçimde LICENSE satırını düzenleyin. Üçüncü taraf
telif bildirimlerini değiştirmeyin veya kaldırmayın.

## 2. Windows ZIP üretme

Python **3.14.2 x64** ve Tkinter ile ayrı ortam kullanın. Bu, lisansları incelenmiş
yerel derleme sürümüdür; en güncel/güvenli Python sürümü olduğu iddiası değildir.
Derleme yorumlayıcısını yükseltirken runtime lisanslarını tekrar inceleyin.
Kaynak kullanımındaki Python 3.12+ desteği bundan ayrıdır.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe scripts/build_windows.py
.venv\Scripts\python.exe scripts/smoke_windows.py
.venv\Scripts\python.exe scripts/package_source.py
```

Alternatif: GitHub Actions → **Windows portable build** → **Run workflow**.
Bu iş akışı yalnız artifact üretir; Release açmaz veya dosya yayımlamaz.
İndirilen Actions artifact'i içindeki taşınabilir ZIP'i Releases'e yükleyin;
artifact'in dış sarmalayıcı ZIP'ini ürün paketiyle karıştırmayın.

Çıktılar `dist/` altındadır. ZIP, uygulama klasörü, runtime dosyaları, README,
lisanslar ve `BUILD_INFO.json` içerir. `SHA256SUMS.txt` ZIP özetini verir.
Derleme bayt düzeyinde yeniden üretilebilirlik veya kod imzası iddiası değildir.

## 3. Yayın öncesi deneme

- `--version`, `--help`, `--list-config` ve salt okunur sentetik tarama geçmeli.
- GUI açılıp kapanmalı; varsayılan yedekleme açık olmalı.
- Python kurulu olmayan temiz Windows VM'de paketi ayrıca deneyin.
- Dosya adları/Unicode yollar, kayıt/yükleme ve geri sarma hedef oyun kopyalarında
  test edilmeli. Asıl oyun ve kayıtlarınıza dokunmayın.
- İmzasız uygulama uyarıları için güvenlik korumasını kapatmayın; kod imzası ve
  false-positive bildirimi ayrı yayın işleri olarak değerlendirilmelidir.
- `licenses/runtime/` ve `BUILD_INFO.json` lisans/bağımlılık listesini inceleyin.

## 4. GitHub Release

İlk etiket: **`v0.1.0b1`**. Bunu **pre-release** olarak işaretleyin.
`CHANGELOG.md` özetini kullanın; Windows ZIP'i ve `SHA256SUMS.txt` yükleyin.
GitHub otomatik kaynak arşivi zaten kaynak dağıtımı sağlar. Başlıkta beta
olduğunu, arayüzün ağırlıklı Türkçe olduğunu ve nötr kararın doğrulanmamış
olabileceğini belirtin. Bütün oyunlarda tüm rotalar garanti edilir demeyin.

## 5. Sonraki sürümler

Sürümün tek kaynağı `renpy_walkthrough_studio.py` içindeki `__version__` değeridir.
CHANGELOG'u güncelleyin, testleri çalıştırın ve yeni artifact üretin. Eski
başarısızlıkları testten silmeyin; atlanan eski API testlerini geçmiş göstermeyin.
