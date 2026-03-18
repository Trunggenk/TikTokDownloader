# Hướng dẫn Phân tích cơ chế tải video và liệt kê đường dẫn video trên Douyin.com (Dựa trên dự án DouK-Downloader)

Tài liệu này sẽ phân tích chi tiết cách dự án `DouK-Downloader` liệt kê tất cả các đường dẫn video trong trang của một người dùng trên Douyin.com và cách thức dự án tải các video này về máy.

## 1. Cơ chế liệt kê tất cả đường dẫn video (Pagination API)

Để lấy được danh sách video của một tài khoản trên Douyin, dự án sử dụng API nội bộ của Douyin thay vì parse (phân tích) HTML của trang web.

### Thông tin API:
- **API Endpoint:** `https://www.douyin.com/aweme/v1/web/aweme/post/` (dành cho video mà người dùng đã đăng tải)
- **API Endpoint (Video yêu thích):** `https://www.douyin.com/aweme/v1/web/aweme/favorite/` (dành cho danh sách video người dùng đã thả tim)
- **Phương thức:** `GET`

### Các tham số quan trọng (Parameters):
Để gọi API này thành công, bạn cần gửi một số tham số (params) bắt buộc:
1. `sec_user_id`: ID định danh ẩn danh (Secure User ID) của tài khoản Douyin. (Mỗi tài khoản có một mã này, thường được trích xuất từ URL chia sẻ profile).
2. `max_cursor`: Dùng để phân trang (pagination).
    - Lần đầu tiên gọi (trang 1): `max_cursor = 0`
    - Các lần gọi tiếp theo: Lấy giá trị `max_cursor` từ JSON response của lần gọi trước.
3. `count`: Số lượng video cần lấy mỗi lần gọi (thường được đặt là `18` hoặc tương tự).
4. Các tham số bổ sung khác như: `version_code`, `version_name`, `device_platform` và đặc biệt là các mã hóa chống bot (ví dụ: cookie `msToken`, `X-Bogus`). Công cụ thường sử dụng cookie đã đăng nhập trên trình duyệt để vượt qua lớp bảo vệ.

### Luồng lấy dữ liệu (File `src/interface/account.py`):
1. **Lần lấy đầu tiên:** Công cụ gửi Request lên API `/post/` với `max_cursor=0`.
2. **Xử lý Response:** Douyin trả về một file JSON. Công cụ sẽ tìm key `"aweme_list"`.
    - Trong list này chứa các object chi tiết của từng video (ID, mô tả, số liệu thống kê, URL video,...).
3. **Phân trang (Pagination):**
    - Kiểm tra key `has_more` trong JSON (nếu bằng `1` hoặc `True`, nghĩa là còn trang tiếp theo).
    - Cập nhật giá trị `max_cursor` từ response hiện tại để làm tham số cho Request tiếp theo.
4. **Vòng lặp:** Tool lặp lại việc gọi API với `max_cursor` mới cho đến khi `has_more == 0`.
5. Từ danh sách `"aweme_list"`, công cụ (tại `src/extract/extractor.py`) trích xuất các đường dẫn tải video (video URL) từ key như `video.bit_rate.play_addr.url_list`.

---

## 2. Cơ chế trích xuất (Extraction) và tải video (Download)

Sau khi có danh sách video, dự án bắt đầu quá trình trích xuất URL và tải chúng về.

### Trích xuất địa chỉ tải (File `src/extract/extractor.py`):
Mỗi phần tử trong `"aweme_list"` chứa thông tin rất chi tiết. Công cụ không lấy video ở độ phân giải ngẫu nhiên mà sẽ tìm bản phân giải cao nhất.
- Truy cập vào cấu trúc: `video` -> `bit_rate`
- `bit_rate` là một mảng (list) chứa các tùy chọn video khác nhau (các độ phân giải, bitrate, FPS).
- Công cụ sắp xếp mảng này theo độ phân giải (ưu tiên `height`, `width`, sau đó là `FPS` và `bit_rate`) để lấy ra URL có chất lượng cao nhất (thường nằm ở `play_addr.url_list[0]`).
- Tương tự với âm thanh (music) hoặc ảnh động (dynamic_cover), ảnh tĩnh.

### Tải video về máy (File `src/downloader/download.py`):
DouK-Downloader sử dụng thư viện **HTTPX** (hỗ trợ bất đồng bộ `async`/`await`) kết hợp với thư viện `aiofiles` để tải video rất nhanh và hỗ trợ tải tiếp khi bị đứt quãng (resume/breakpoint resume).

1. **Chuẩn bị Header:**
    - Request tải video cần các Header đặc biệt, điển hình nhất là giả lập `User-Agent` hợp lệ.
2. **Cơ chế Resume (Range Header):**
    - Kiểm tra xem file video tạm thời (cache file) đã có trên ổ cứng chưa.
    - Nếu có, đọc dung lượng hiện tại của file (ví dụ `N` bytes).
    - Thêm Header `Range: bytes={N}-` vào Request. Server Douyin sẽ chỉ trả về phần dữ liệu còn lại thay vì tải lại từ đầu.
3. **Download theo dạng luồng (Streaming):**
    - Thay vì tải nguyên một file dung lượng lớn vào RAM, nó sử dụng `client.stream("GET", url)`.
    - Nhận dữ liệu từng phần (chunk) (thường khoảng 1MB mỗi chunk) và sử dụng `aiofiles.open(file, 'ab')` (append mode) để nối dữ liệu đó vào file đang tải.
    - Trong khi tải, công cụ cập nhật quá trình (progress bar) trên màn hình terminal bằng thư viện `rich`.
4. **Kết thúc quá trình tải:**
    - Khi tải xong toàn bộ các chunk, file tạm được chuyển đổi định dạng và đổi tên/di chuyển sang thư mục lưu trữ đích (ví dụ: `UID_12345_发布作品/`).
    - Lưu trạng thái đã tải (bằng cơ sở dữ liệu SQLite: aiosqlite qua `DownloadRecorder`) để lần chạy sau công cụ sẽ bỏ qua file này nếu ID video đã có trong database.

### Tóm tắt luồng hoạt động:
- Lấy sec_user_id -> Gọi API pagination (`/aweme/post/`) lấy cục bộ danh sách `"aweme_list"` -> Cắt lấy list các URL chất lượng cao -> Gửi Request tải kiểu streaming kèm Header `Range` -> Ghi ra file -> Ghi log vào cơ sở dữ liệu hoàn thành.
