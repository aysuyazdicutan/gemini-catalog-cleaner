# Gemini Ürün Katalog Temizleme Projesi

Bu proje, Google Gemini AI kullanarak Excel dosyasındaki ham ürün verilerini temizleyen ve standardize eden bir Python scriptidir.

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

## Kullanım

1. `urunler_ham.xlsx` adında bir Excel dosyası hazırlayın ve proje klasörüne koyun.
2. Excel dosyasında en azından `Baslik` sütunu bulunmalıdır.
3. Scripti çalıştırın:
```bash
python main.py
```

4. İşlem tamamlandığında `urunler_temiz.xlsx` dosyası oluşturulacaktır.

## Özellikler

- Başlıklardan gereksiz bilgileri temizler
- Kısaltmaları tanır ve açılımlarını yapar
- Renk ve teknik terimleri Türkçe'ye çevirir
- Veri formatlarını standardize eder
- Çelişkileri tespit eder ve uyarı verir

## Notlar

- API rate limit'i nedeniyle her satır arasında 1 saniye bekleme yapılır
- Test için script içinde `df.iterrows()` yerine `df.iterrows()[:5]` kullanabilirsiniz





