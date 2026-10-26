# Kamu Analiz Merkezi — Online V2

## Program
Tarayıcıda HTML arayüzü ile çalışan Flask tabanlı çevrimiçi birim fiyat analiz uygulaması.

- 2.624 adet başlangıç fiyat kaydı: ÇŞB 2026-10 ve KGM 2026-01. Bunlar **analiz girdisi rayiçlerinin tam listesi değildir**.
- Poz numarasına göre açık kaynak analiz tablolarını arama ve okumayı deneme.
- KGM/15.150/K örneği (0,25 saat düz işçi): canlı siteden okunamazsa **önceden kaydedilmiş örnek** olduğu ayrıca belirtilir.
- Aylık rayiçleri CSV/PDF veya tek tek yükleme; SQLite saklama ve JSON yedekleme.
- Eksik rayiç varken kesin toplam hesaplamama, girdilerin kaynaklarını gösterme.

## Yayınlama — kullanıcı adımları
1. ZIP dosyasını açın. `app.py`, `requirements.txt`, `render.yaml`, `templates` ve `data` klasörlerini bir **GitHub deposuna** yükleyin.
2. https://dashboard.render.com/ adresinde hesabınıza giriş yapın; **New > Blueprint** seçip GitHub deponuzu bağlayın. `render.yaml` kurulum ayarlarını içerir.
3. Yayın tamamlanınca Render'ın verdiği HTTPS adresini açın. HTML ekranına oradan ulaşacaksınız.
4. `KGM/15.150/K` yazıp analizi aratın. Rayiçler sekmesinden 2026-10 dönemine ilgili resmî fiyatı yükleyin veya tek girdi olarak girin. Kaynak durumunu ve hesabı kontrol edin.

## Yerel geliştirici testi
`pip install -r requirements.txt`
`python app.py`
Tarayıcı: http://localhost:5000

## Kritik sınırlamalar
- Bu ZIP **canlı site değildir**. Hesap açılması, GitHub deposu ve Render üzerinden yayınlama gerektirir.
- İnternet araması Bing/Google sayfa yapısına ve erişimine bağlıdır; garanti değildir. İzin verilen kaynakların analiz URL'sini doğrudan girme seçeneği vardır.
- Ücretli / oturum gerektiren analizlere erişmez. Her pozun sayısal analizi bulunamayabilir.
- Yüklenen PDF rayiçleri otomatik ayrıştırılır; satır bölünmesi, fiyatın yanlış sütundan alınması gibi riskler vardır. Kullanıcı mutlaka kontrol etmelidir.
- KGM/15.150/K dışında bütün KGM pozları için doğrulanmış analiz verisi bulunmamaktadır.
- 2026-10 resmî KGM ve ÇŞB **tüm rayiç girdi fiyatları** programa önceden yüklenmemiştir.
- SQLite yerel süreç yeniden başlasa da dosyada kalır; Render'ın ücretsiz geçici diski yeniden dağıtımda sıfırlanabilir. JSON yedek alın veya kalıcı disk yapılandırın.
- Genel gider/kâr oranı her poz için otomatik mevzuat kontrolünden geçmez; kullanıcı doğrulamalıdır.
- Bu araç ön hesaplamadır, ihale ve hakediş için resmî analizlerle doğrulama gerekir.

## Güvenlik
Web kaynağı alma izinli HTTPS alan adlarıyla sınırlıdır; üçüncü taraf kaynak içeriği güvenilir kabul edilmez. Kamuya açık sunucuya koyarken kullanıcı doğrulama, istek sınırı ve kalıcı veritabanı eklenmesi önerilir.
