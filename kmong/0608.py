from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from openpyxl import Workbook
from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from kiwipiepy import Kiwi
from collections import Counter
import time
import datetime
import requests
import traceback
import re

# ✅ 키워드 추출 함수
def extract_keywords(reviews, top_n=10):
    kiwi = Kiwi()
    stopwords = {'수', '것', '정도', '때', '이', '가', '은', '는', '을', '를', '에', '의', '로'}
    tokens = []
    for text in reviews:
        for token in kiwi.tokenize(text):
            if token.tag.startswith("NN") and len(token.form) > 1 and token.form not in stopwords:
                tokens.append(token.form)
    return Counter(tokens).most_common(top_n)

# ✅ 장소명 → place_id 추출 함수 (XPath 기반 클릭)
def get_place_id_from_name(place_name, driver):
    driver.get(f"https://map.naver.com/v5/search/{place_name}")
    wait = WebDriverWait(driver, 15)

    # 검색 결과 iframe 진입
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))

    # 정확한 XPath로 첫 번째 장소 클릭
    xpath = '//*[@id="_pcmap_list_scroll_container"]/ul/li[1]/div[1]/div[1]/a'
    first_place = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].click();", first_place)

    # 주소창 URL 반영을 기다림
    driver.switch_to.default_content()
    time.sleep(2)
    current_url = driver.current_url

    match = re.search(r'/place/(\d+)', current_url)
    if match:
        return match.group(1)
    else:
        raise Exception(f"URL에서 ID를 찾을 수 없습니다: {current_url}")

# ✅ 실행 시작
place_name = input("리뷰를 수집할 장소명을 입력하세요: ").strip()

options = webdriver.ChromeOptions()
# options.add_argument('headless')  # 눈으로 확인 시 주석 유지
options.add_argument('window-size=1920x1080')
options.add_argument("disable-gpu")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

now = datetime.datetime.now()
xlsx = Workbook()
list_sheet = xlsx.active
list_sheet.title = 'reviews'
list_sheet.append(['nickname', 'content', 'date', 'revisit'])

review_texts = []

try:
    # ✅ 장소 ID 추출
    place_id = get_place_id_from_name(place_name, driver)
    print(f"[INFO] 장소명 '{place_name}' → ID: {place_id}")

    # ✅ 리뷰 페이지로 이동
    review_url = f'https://m.place.naver.com/restaurant/{place_id}/review/visitor?entry=ple&reviewSort=recent'
    driver.get(review_url)
    driver.implicitly_wait(30)

    for _ in range(10):
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)

    try:
        for _ in range(30):
            driver.find_element(By.XPATH, '//*[@id="app-root"]/div/div/div/div[6]/div[2]/div[4]/div[2]/div/a/span').click()
            time.sleep(0.4)
    except Exception:
        print('더보기 버튼 클릭 종료')

    time.sleep(5)
    html = driver.page_source
    bs = BeautifulSoup(html, 'lxml')
    reviews = bs.select('li.place_apply_pui.EjjAW')

    for r in reviews:
        nickname = r.select_one('div.pui__JiVbY3 > span.pui__uslU0d')
        content = r.select_one('div.pui__vn15t2 > a')
        date_elements = r.select('div.pui__QKE5Pr > span.pui__gfuUIT > time')
        date = date_elements[0] if date_elements else 'N/A'
        revisit_span = r.select('div.pui__QKE5Pr > span.pui__gfuUIT')
        revisit = revisit_span[1] if len(revisit_span) > 1 else 'N/A'

        nickname = nickname.text if nickname else ''
        content = content.text if content else ''
        date = date.text if date else ''
        revisit = revisit.text if revisit else ''
        time.sleep(0.06)

        print(nickname, '/', content, '/', date, '/', revisit)
        list_sheet.append([nickname, content, date, revisit])
        if content:
            review_texts.append(content)
        time.sleep(0.06)

    driver.quit()

    file_name = f'naver_review_{now.strftime("%Y-%m-%d_%H-%M-%S")}.xlsx'
    xlsx.save(file_name)
    print(f"\n📁 파일이 저장되었습니다: {file_name}")
    print(f"시트 '{list_sheet.title}'에 총 {list_sheet.max_row-1}개의 리뷰가 저장되었습니다.")

    # ✅ 키워드 출력
    keywords = extract_keywords(review_texts, top_n=10)
    print("\n📌 리뷰 키워드 TOP 10")
    for word, count in keywords:
        print(f"{word}: {count}회")

except Exception as e:
    print(f"\n❌ 크롤링 중 오류 발생: {e}")
    try:
        driver.quit()
    except:
        pass
    file_name = f'naver_review_{now.strftime("%Y-%m-%d_%H-%M-%S")}_error.xlsx'
    xlsx.save(file_name)
    print(f"⚠️ 오류 발생으로 임시 파일 저장됨: {file_name}")
