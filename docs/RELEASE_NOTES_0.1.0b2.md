# v0.1.0b2 — Yazım güvenliği düzeltmesi

İlk GitHub CI çalışmasında üç Windows işi geçti; üç Linux işi aynı eşzamanlı dosya
değişikliği testinde başarısız oldu. Linux dosya sırası, daha önce görünmeyen gerçek
bir yazım güvenliği açığını ortaya çıkardı.

## Düzeltilen sorun

Uygulama, bir dosyayı yamaladıktan hemen sonra başka bir programın o dosyada yaptığı
değişikliği kendi yazımı sanarak sonraki dosyaları eski analize göre yamalayabiliyordu.
Artık uygulamanın yazdığı geçici dosyanın zaman/boyut bilgisi hedefe taşınmadan önce
kaydediliyor ve her yazımdan hemen sonra bütün izlenen kaynaklar kontrol ediliyor.
Değişiklik saptanınca sonraki yazımlar durduruluyor; dış değişiklik korunuyor.

Bu genel bir dosya kilidi/transaction garantisi değildir. Çalışma sırasında oyun
kaynaklarını başka bir programla düzenlemeyin; daima ayrı oyun kopyası kullanın.
Analiz algoritması, renk kuralları ve mevcut güvenlik sınırları gevşetilmedi.

## Testler

Mevcut regresyon dört farklı ilk dosyayla, hem o dosyada hem farklı bir dosyada
dış değişiklik yapılarak çalıştırılıyor. Eski kodun hatası Windows'ta da bu sıralarla
yeniden üretildi. Linux testleri kaldırılmadı; testler atlanarak geçirilmedi.
Güncel doğrulama bilgileri `docs/VALIDATION.md` dosyasındadır.

- GitHub CI: Windows/Linux × Python 3.12, 3.13, 3.14 — **6/6 iş geçti**.
- Test paketi: **263 başarılı, 52 eski API sözleşmesi açıkça atlandı** (315 toplam).
- İki yerel Ren'Py motorunda **149/149 native senaryo geçti**; uygulama hash'leri eşleşti.
- Windows EXE sürüm/yardım/yapılandırma, salt okunur Unicode-yol taraması ve GUI
  aç/kapat kontrollerini geçti. Temiz VM veya imzalı paket iddiası değildir.

## İndirme ve kullanım

- Windows x64: `RenpyWalkthroughStudio-0.1.0b2-windows-x64.zip`; tamamını çıkarın,
  EXE ile `_internal` klasörünü birlikte tutun. Python gerekmez.
- Kaynak: `renpy-walkthrough-studio-0.1.0b2-source.zip` veya GitHub kaynak arşivi.
  Python 3.12+; GUI bağımlılıkları `requirements-gui.txt` içinde.
- Dosya özetleri: `SHA256SUMS.txt`.

`v0.1.0b1` yerine bu sürümü kullanın. Eski etiket ve dosyalar sessizce değiştirilmez.
Paket imzasızdır; temiz Windows VM kontrolü ve kod imzalama yapılmış sayılmamalıdır.
