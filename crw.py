import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from collections import Counter
from kiwipiepy import Kiwi
import chromedriver_autoinstaller

class NaverMapCrawler:
    def __init__(self):
        self.kiwi = Kiwi()
        self.driver = self.setup_driver()
        self.wait = WebDriverWait(self.driver, 15)  # 대기 시간 증가

    def setup_driver(self):
        """크롬 드라이버 설정"""
        chromedriver_autoinstaller.install()
        options = Options()
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=options)

    def extract_keywords(self, texts, top_n=15):
        """Kiwi를 이용한 키워드 추출"""
        nouns = []
        stopwords = ['수', '것', '등', '좀', '정도', '이', '가', '의', '을', '를', '은', '는', '에', '와', '과', '도', '로']
        
        for text in texts:
            for token in self.kiwi.tokenize(text):
                if (token.tag.startswith('NNG') or token.tag.startswith('NNP')) and len(token.form) > 1 and token.form not in stopwords:
                    nouns.append(token.form)
        
        return Counter(nouns).most_common(top_n)

    def crawl_naver_map(self, keyword, max_places=10):
        """네이버 지도에서 장소 정보 크롤링 (XPath 사용)"""
        try:
            # 검색 실행
            self.driver.get("https://map.naver.com/v5")
            search_box = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/div[2]/div[1]/div/div[1]/div/div')))
            search_box.send_keys(keyword + Keys.ENTER)
            time.sleep(2)

            # 검색 프레임 전환
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="searchIframe"]')))

            results = {}
            place_count = 0

            while place_count < max_places:
                # 장소 목록 가져오기 (XPath 사용)
                places = self.wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "ouxiq")]/a[contains(@class, "tzwk0")]'))
                )

                for place in places[place_count:place_count+3]:
                    try:
                        place_name = place.text.strip()
                        if not place_name or place_name in results:
                            continue

                        # 장소 클릭 (XPath 사용)
                        self.driver.execute_script("arguments[0].click();", place)
                        time.sleep(1.5)

                        # 상세 정보 수집
                        place_data = self.collect_place_details(place_name)
                        results[place_name] = place_data
                        place_count += 1

                        # 검색 프레임으로 복귀
                        self.driver.switch_to.default_content()
                        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="searchIframe"]')))

                    except Exception as e:
                        print(f"[에러] {place_name} 처리 실패:", str(e))
                        continue

                # 스크롤 다운
                self.driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(1)

                if place_count >= max_places:
                    break

            return results

        except Exception as e:
            print("[에러] 크롤링 중 오류 발생:", str(e))
            return {}

    def collect_place_details(self, place_name):
        """개별 장소 상세 정보 수집 (XPath 사용)"""
        data = {
            "name": place_name,
            "reviews": [],
            "keywords": [],
            "basic_info": {}
        }

        try:
            # 상세 프레임 전환
            self.driver.switch_to.default_content()
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@id="entryIframe"]')))

            # 기본 정보 수집 (XPath 사용)
            try:
                info_sections = self.driver.find_elements(By.XPATH, '//div[contains(@class, "place_section_content")]')
                for section in info_sections:
                    try:
                        title = section.find_element(By.XPATH, './/h2').text
                        content = section.find_element(By.XPATH, './/div[contains(@class, "O8qbU")]').text
                        data["basic_info"][title] = content
                    except:
                        continue
            except:
                pass

            # 리뷰 수집 (XPath 사용)
            try:
                self.wait.until(EC.element_to_be_clickable((By.XPATH, '//span[contains(text(), "리뷰")]/..'))).click()
                time.sleep(2)

                reviews = set()
                for _ in range(3):  # 3번 스크롤
                    self.driver.execute_script("window.scrollBy(0, 500)")
                    time.sleep(1.5)
                    new_reviews = self.driver.find_elements(By.XPATH, '//div[contains(@class, "pui__vn15t2")]/a/span')
                    reviews.update(r.text for r in new_reviews if r.text.strip() and len(r.text) > 5)

                data["reviews"] = list(reviews)[:100]  # 최대 100개 리뷰
                data["keywords"] = self.extract_keywords(data["reviews"])

            except Exception as e:
                print(f"[경고] {place_name} 리뷰 수집 실패:", str(e))

        except Exception as e:
            print(f"[에러] {place_name} 상세 정보 수집 실패:", str(e))

        return data

    def run(self):
        """프로그램 실행"""
        print("=== 네이버 지도 리뷰 키워드 분석기 ===")
        keyword = input("검색할 장소를 입력하세요: ").strip()
        max_places = int(input("수집할 최대 장소 수 (기본 10): ") or 10)

        print(f"\n[{keyword}] 검색 시작...")
        results = self.crawl_naver_map(keyword, max_places)

        # 결과 저장
        filename = f"naver_map_{keyword}_results.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n※ 결과가 {filename} 파일로 저장되었습니다.")
        self.driver.quit()

        # 키워드 종합 분석
        all_reviews = []
        for place in results.values():
            all_reviews.extend(place["reviews"])

        if all_reviews:
            total_keywords = self.extract_keywords(all_reviews, 20)
            print("\n=== 전체 종합 키워드 TOP 20 ===")
            for word, count in total_keywords:
                print(f"{word}: {count}회")

if __name__ == "__main__":
    crawler = NaverMapCrawler()
    try:
        crawler.run()
    except Exception as e:
        print("프로그램 실행 중 오류 발생:", str(e))
        crawler.driver.quit()