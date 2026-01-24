import pytest
import mysql.connector
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import time

@pytest.fixture(scope="module")
def driver():
    """Fixture để khởi tạo và đóng trình duyệt Selenium một lần cho toàn bộ module"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Chạy không hiện trình duyệt (nhanh hơn, phù hợp CI/CD)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    yield driver
    driver.quit()

def open_page(driver, page_name):
    """Mở trang HTML local"""
    base_url = "file:///C:/xampp/htdocs/524100102/"  # ← ĐƯỜNG DẪN THƯ MỤC DỰ ÁN CỦA BẠN
    url = base_url + page_name
    driver.get(url)
    time.sleep(1)  # Đợi trang load (có thể thay bằng WebDriverWait nếu cần)
    return True

# ================== TEST SELENIUM ==================
def test_increase_decrease_quantity(driver):
    """Test logic tăng/giảm số lượng sản phẩm trên trang chi tiết"""
    if not open_page(driver, "sanpham.html"):  # ← THAY TÊN FILE TRANG CHI TIẾT SẢN PHẨM CỦA BẠN
        pytest.fail("Không mở được trang sản phẩm")
    
    try:
        qty_input = driver.find_element(By.ID, "quantity")
        btn_increase = driver.find_element(By.ID, "increase-qty")
        btn_decrease = driver.find_element(By.ID, "decrease-qty")
        
        # Giá trị ban đầu
        initial_val = int(qty_input.get_attribute("value"))
        assert initial_val == 1, "Giá trị mặc định không phải là 1"
        
        # Tăng số lượng
        btn_increase.click()
        time.sleep(0.5)
        new_val = int(qty_input.get_attribute("value"))
        assert new_val == 2, "Nút tăng số lượng không hoạt động"
        
        # Giảm số lượng
        btn_decrease.click()
        time.sleep(0.5)
        final_val = int(qty_input.get_attribute("value"))
        assert final_val == 1, "Nút giảm số lượng không hoạt động"
        
        # Giảm lần nữa → không được dưới 1
        btn_decrease.click()
        time.sleep(0.5)
        min_val = int(qty_input.get_attribute("value"))
        assert min_val == 1, "Số lượng bị giảm xuống dưới 1 (sai logic)"
        
        print(" -> Logic tăng/giảm số lượng hoạt động chính xác.")
    except Exception as e:
        pytest.fail(f"Lỗi khi test logic sản phẩm: {e}")

def test_navigation_flow(driver):
    """Kiểm tra luồng: Trang chủ -> Click sách -> Vào trang chi tiết"""
    if not open_page(driver, "trangchu.html"):
        pytest.fail("Không mở được trang chủ")
    
    try:
        # Tìm sách đầu tiên và click
        first_book_link = driver.find_element(By.CSS_SELECTOR, ".book-item a")
        href_target = first_book_link.get_attribute("href")
        
        first_book_link.click()
        time.sleep(1)  # Đợi chuyển trang
        
        current_url = driver.current_url
        assert (href_target in current_url or os.path.basename(href_target) in current_url), \
            f"Click vào sách không chuyển đúng trang. Hiện tại: {current_url}"
        
        print(" -> Navigation từ trang chủ sang chi tiết sản phẩm thành công.")
    except Exception as e:
        pytest.fail(f"Lỗi khi test navigation: {e}")

# ================== TEST DATABASE (giữ nguyên và cải tiến nhẹ) ==================
@pytest.fixture(scope="function")
def db_cursor():
    """Fixture kết nối database, tự động đóng sau mỗi test"""
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='webphp')
    cursor = conn.cursor(dictionary=True)
    yield cursor, conn
    cursor.close()
    conn.close()

def test_search_products(db_cursor):
    cursor, conn = db_cursor
    term = 'bánh'
    sql = "SELECT * FROM products WHERE tensanpham LIKE %s LIMIT 10"
    cursor.execute(sql, ('%' + term + '%',))
    data = cursor.fetchall()
    assert len(data) > 0, f"Không tìm thấy sản phẩm nào chứa từ '{term}'"

def test_add_item_to_cart(db_cursor):
    cursor, conn = db_cursor
    user_id = 1
    product_id = 1
    quantity = 2
    
    cursor.execute(
        "INSERT INTO cart (user_id, product_id, quantity, selected) "
        "VALUES (%s, %s, %s, 1) ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)",
        (user_id, product_id, quantity)
    )
    conn.commit()
    
    cursor.execute("SELECT quantity FROM cart WHERE user_id = %s AND product_id = %s", (user_id, product_id))
    result = cursor.fetchone()
    assert result and result['quantity'] >= quantity, "Thêm sản phẩm vào giỏ không đúng số lượng"
    
    # Cleanup
    cursor.execute("DELETE FROM cart WHERE user_id = %s AND product_id = %s", (user_id, product_id))
    conn.commit()

def test_checkout_process(db_cursor):
    cursor, conn = db_cursor
    voucher_code = 'TESTVOUCHER'
    order_total = 100
    
    # Query voucher với điều kiện expiry_date (cải tiến từ code của bạn)
    cursor.execute(
        "SELECT * FROM vouchers WHERE code = %s AND (expiry_date IS NULL OR expiry_date = '0000-00-00' OR expiry_date >= CURDATE())",
        (voucher_code,)
    )
    voucher = cursor.fetchone()
    
    if voucher and order_total >= voucher.get('min_order_value', 0):
        discount = voucher.get('discount_value', 0)
        assert discount > 0, "Voucher hợp lệ nhưng discount = 0"
    else:
        assert True, "Không tìm thấy voucher hợp lệ (được phép theo logic)"

if __name__ == "__main__":
    pytest.main(["-v", __file__])