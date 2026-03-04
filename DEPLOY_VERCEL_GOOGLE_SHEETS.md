# Deploy Vercel + Google Sheets + Search Console

## 1. Mục tiêu

- Public website trên Vercel để gửi link cho khách.
- Form liên hệ ghi thẳng vào Google Sheets.
- Có `robots.txt` và `sitemap.xml` để đưa vào Google Search Console.

## 2. File đã chuẩn bị

- `public/index.html`: website tĩnh public
- `api/contact.py`: serverless API ghi dữ liệu vào Google Sheets
- `requirements.txt`: dependencies cho Vercel Python runtime
- `vercel.json`: config deploy cơ bản
- `public/robots.txt`
- `public/sitemap.xml`
- `.env.example`: mẫu biến môi trường

## 3. Chuẩn bị Google Sheets

1. Tạo một Google Sheet mới.
2. Lấy `spreadsheet id` từ URL:
   - Ví dụ: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`
3. Tạo Google Cloud Project.
4. Enable `Google Sheets API`.
5. Tạo `Service Account`.
6. Tạo key dạng JSON cho service account.
7. Chia sẻ Google Sheet cho email của service account với quyền `Editor`.

## 4. Biến môi trường cần thêm trên Vercel

Thêm các biến sau trong Vercel Project Settings > Environment Variables:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
  - Dán nguyên nội dung JSON key của service account
- `GOOGLE_SHEET_ID`
  - ID của Google Sheet
- `GOOGLE_SHEET_NAME`
  - Ví dụ: `Contacts`
- `SITE_URL`
  - Domain public thật của website, ví dụ `https://th-ecohome.vn`

## 5. Deploy lên Vercel

1. Đưa thư mục này lên GitHub.
2. Vào Vercel > `Add New Project`.
3. Import repo chứa thư mục `00. CODE TEST/Kudo`.
4. Chọn đúng Root Directory là:
   - `00. CODE TEST/Kudo`
5. Thêm các Environment Variables ở bước 4.
6. Deploy.

## 6. Sau khi có domain thật

Bạn cần sửa 2 file này:

- `public/robots.txt`
- `public/sitemap.xml`

Thay `https://your-domain.example` bằng domain thật, ví dụ:

- `https://th-ecohome.vn`

Sau đó deploy lại.

## 7. Thêm site vào Google Search Console

Việc này phải làm trong tài khoản Google của bạn.

Khuyến nghị:

1. Mở Google Search Console.
2. Chọn `Add property`.
3. Nếu có domain riêng, nên dùng `Domain property`.
4. Xác minh bằng DNS.
5. Sau khi verified, vào mục `Sitemaps`.
6. Gửi:
   - `https://your-domain.example/sitemap.xml`

## 8. Kiểm tra luồng form

Sau khi deploy:

1. Mở website public.
2. Gửi thử form liên hệ.
3. Mở Google Sheet.
4. Kiểm tra đã có dòng mới trong sheet `Contacts`.

## 9. Lưu ý

- Nếu chưa share Google Sheet cho service account thì form sẽ lỗi.
- Nếu `GOOGLE_SERVICE_ACCOUNT_JSON` sai định dạng thì API sẽ lỗi.
- Nếu chưa đổi domain trong `robots.txt` và `sitemap.xml`, Google vẫn đọc được file nhưng URL sẽ sai.
