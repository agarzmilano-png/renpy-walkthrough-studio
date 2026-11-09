# Türkçe kullanım

## Kaynaktan çalıştırma

Python 3.12+ kullanın. Windows için resmî Python kurulumunda Tkinter seçeneğini
koruyun. Sistem paketlerini değiştirmemek için proje klasöründe sanal ortam önerilir:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.venv\Scripts\python.exe renpy_walkthrough_studio.py
```

Aktivasyon veya PowerShell güvenlik politikasını değiştirmek gerekmez. CLI için
CustomTkinter zorunlu değildir. `psutil` ek süreç tespiti için isteğe bağlıdır.

## Taşınabilir Windows paketi

GitHub Releases üzerinden sunulan Windows ZIP'ini **tamamıyla** ayrı bir klasöre
çıkarın. `RenpyWalkthroughStudio.exe` ile `_internal` klasörünü birlikte tutun;
yalnız EXE'yi başka yere taşımayın. Python kurulu olması gerekmez.

Sürüm ve yardım:

```powershell
.\RenpyWalkthroughStudio.exe --version
.\RenpyWalkthroughStudio.exe --help
```

CLI desteği ve hata çıktıları korunabilsin diye konsol açık bırakılmıştır.
İmzasız beta paketleri SmartScreen/antivirüs uyarısı verebilir. Korumayı kapatmayın;
SHA-256'yı karşılaştırın, gerekirse kaynak sürümü tercih edin.

## Güvenli çalışma sırası

1. Oyunu kapatın. **Oyun klasörünün tamamının ayrı bir kopyasını alın.**
2. Uygulamaya orijinal yerine bu kopyayı gösterin.
3. Önce salt okunur tarama yapın ve raporu inceleyin.
4. Yedekleme açıkken kopyaya yama uygulayın.
5. Oyunu bu kopyadan açarak seçim, kayıt/yükleme ve geri sarma davranışını deneyin.

Örnek CLI taraması; rapor klasörünü önceden oluşturun:

```powershell
python renpy_walkthrough_studio.py "C:\OyunKopyasi" --cli --scan --detect-both --report "C:\Raporlar\analiz.json" --both-report "C:\Raporlar\both.json"
```

Yama:

```powershell
python renpy_walkthrough_studio.py "C:\OyunKopyasi" --cli --apply-both --no-cheat-menu
```

Hazır `.rpy` kaynaklarınız varsa `--skip-rpa` kullanılabilir. Otomatik `.wtbak`
yedeklerini kapatmayın. Kaynak/motor uyumluluğu garanti edilmeyen bir oyunda
önce kayıtlarınızı ayrıca koruyun; yama eski kayıtların tamamını garanti etmez.
Kapsül çalıştırma izni isteyen seçenekleri güvenmediğiniz dosyalarda kullanmayın.

## Renkler

- Nötr, “etkisiz” veya “kesin güvenli” değil; sonuç doğrulanmamış olabilir.
- Diyalogdaki ölüm/iyi son sözleri ve label adları tek başına kanıt değildir.
- Koşul/eşik sağlanması tek başına ödül sayılmaz.
- Menüye gelen durum ve gerçek çağıran izlenir; farklı değerler bilinmeyen kalabilir.
- Both/All yalnız desteklenen kaynak sahne planlarında eklenir. Reddedilen bir
  yapıyı sırf seçenek oluşsun diye zorlamak doğru değildir.

Rehber/LLM/API anahtarı gerekmez. Türkçe arayüz ve ipuçları mevcut; bütün oyunlarda
tüm rota sonlarını garanti eden bir motor değildir. Kapsam: [ANALYSIS.md](ANALYSIS.md).

## Sorun bildirme

`--version` çıktısını, Python/Windows ve Ren'Py sürümünü, kullanılan seçenekleri
ve mümkünse **kendi hazırladığınız küçük bir sentetik örneği** ekleyin.
Tam oyun, arşiv, kayıt, özel dosya yolu veya hesap bilgisi yüklemeyin.
