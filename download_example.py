import asyncio
import sys
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn để có thể import các thư viện của DouK-Downloader
sys.path.append(str(Path(__file__).parent))

from src.testers.params import Params
from src.interface.detail import Detail
from src.extract.extractor import Extractor
from src.downloader.download import Downloader
from src.custom.internal import DOWNLOAD_HEADERS


# Tạo một mock Console để vá lỗi không có hàm warning của thư viện rich
class MockConsole:
    def print(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        print("Cảnh báo:", *args)

    def error(self, *args, **kwargs):
        print("Lỗi:", *args)

    def info(self, *args, **kwargs):
        print("Thông tin:", *args)


# Tạo một mock recorder giả để phục vụ DownloadRecorder vì chạy bên ngoài framework cần Database
class MockRecorder:
    async def has_id(self, id_: str) -> bool:
        return False

    async def update_id(self, id_: str):
        pass

    async def delete_id(self, id_: str):
        pass


async def download_single_video(url_or_id: str):
    # ID của video cần tải. Trong url https://www.douyin.com/video/7431470164819905811 thì id là 7431470164819905811
    video_id = url_or_id.split("/")[-1] if "/" in url_or_id else url_or_id
    print(f"Bắt đầu lấy thông tin video ID: {video_id}")

    # Sử dụng Params() để cung cấp httpx client, header và config cơ bản
    async with Params() as params:
        # Cấu hình một số thứ cơ bản bị thiếu cho test case
        params.folder_name = "Download"
        params.root = Path("./")
        params.split = "_"
        params.name_format = ["id", "desc"]
        params.name_length = 50
        params.desc_length = 50
        params.folder_mode = False
        params.music = False
        params.dynamic_cover = False
        params.static_cover = False
        params.download = True
        params.max_size = 0
        params.chunk = 1024 * 1024
        params.max_retry = 3
        params.timeout = 10
        params.ffmpeg = None
        params.cache = Path("./cache")
        params.cache.mkdir(exist_ok=True)
        params.truncate = 50
        params.recorder = MockRecorder()

        # Cài đặt cookie của bạn vào Request Headers
        # Mặc định script sẽ lấy Cookie từ Params (thường cấu hình trong file test_cookie.ini)
        # Ở đây tôi ví dụ đặt một biến string trống, nếu bạn có Cookie, hãy dán vào đây:
        user_cookie = ""

        if user_cookie:
            params.headers["Cookie"] = user_cookie
            params.cookie_str = user_cookie
        params.headers_download = DOWNLOAD_HEADERS  # Sửa Header tải về Douyin
        params.headers_download_tiktok = params.headers_download
        params.proxy_tiktok = params.proxy
        params.console = MockConsole()  # Mock Console

        # 1. Gọi API lấy dữ liệu thô của Douyin
        detail_api = Detail(params, cookie=user_cookie, detail_id=video_id)
        raw_data = await detail_api.run()

        if not raw_data:
            print("Không thể lấy dữ liệu từ video này (Có thể cần cập nhật Cookie trong src/testers/params.py).")
            return

        # 2. Extract thông tin URL tải video
        extractor = Extractor(params)

        class MockRecord:
            def __init__(self):
                self.field_keys = []
            async def save(self, data):
                pass

        extracted_data = await extractor.run([raw_data], recorder=MockRecord(), type_="detail", tiktok=False)

        if not extracted_data:
            print("Trích xuất thông tin video thất bại.")
            return

        print(f"Đã trích xuất dữ liệu, chuẩn bị tải: {extracted_data[0].get('desc')}")

        # 3. Tiến hành tải video
        downloader = Downloader(params, server_mode=True)
        await downloader.run(extracted_data, type_="detail", tiktok=False)
        print("Quá trình tải video hoàn tất!")

if __name__ == "__main__":
    url = "https://www.douyin.com/video/7431470164819905811"
    asyncio.run(download_single_video(url))
