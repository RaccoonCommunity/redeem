from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import json
import os

app = Flask(__name__)

USED_ORDERS_FILE = 'used_orders.json'

def load_used_orders():
    if not os.path.exists(USED_ORDERS_FILE):
        return set()
    with open(USED_ORDERS_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return set(data)
        except:
            return set()

def save_used_orders(orders_set):
    with open(USED_ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(orders_set), f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/topup", methods=["POST"])
def topup():
    data = request.get_json()
    success, message = selenium_api_check(data)
    return jsonify(success=success, message=message)

def selenium_api_check(data):
    used_orders = load_used_orders()

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://xiaoxingshop.com/#/CustCardExchange")
        time.sleep(3)

        game_map = {
            "genshin": '/html/body/div/section/main/div/span[3]',
            "starrail": '/html/body/div/section/main/div/span[4]',
            "zzz": '/html/body/div/section/main/div/span[5]',
        }

        driver.find_element(By.XPATH, game_map[data['game']]).click()
        time.sleep(1)

        driver.find_element(By.XPATH, '(//input[@class="el-input__inner"])[1]').send_keys(data['cardNumber'])
        driver.find_element(By.XPATH, '(//input[@class="el-input__inner"])[2]').send_keys(data['uid'])
        driver.find_element(By.XPATH, '(//input[@placeholder="请选择"])[1]').click()
        time.sleep(0.5)
        driver.find_element(By.XPATH, f'//span[contains(text(), "{data["server"]}")]').click()
        time.sleep(0.5)

        driver.find_element(By.XPATH, '//*[@id="app"]/section/main/form/div[4]/div/button[1]').click()
        time.sleep(8)

        logs = driver.get_log('performance')

        for entry in logs:
            try:
                msg = json.loads(entry['message'])['message']
                if msg.get('method') == 'Network.responseReceived':
                    resp = msg['params']['response']
                    url = resp.get('url', '')
                    if 'Query?card_no=' in url and resp.get('status') == 200:
                        request_id = msg['params']['requestId']
                        resp_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                        body = resp_body.get('body', '')

                        outer_json = json.loads(body)
                        if outer_json.get('code') == 200 and outer_json.get('data'):
                            inner_str = outer_json['data'].strip()
                            inner_json = json.loads(inner_str)
                            order_id = inner_json.get('order_id', '')
                            order_status = inner_json.get('order_status', '')

                            if order_id in used_orders:
                                return False, "⚠️ 此訂單已儲值過，請勿重複使用"

                            if order_status == 'completed':
                                used_orders.add(order_id)
                                save_used_orders(used_orders)
                                return True, "✅ 儲值成功"
                            else:
                                return False, f"❌ 訂單狀態：{order_status}"
                        else:
                            return False, "❌ API 無資料，請重試或聯繫工作人員"
            except Exception as e:
                return False, f"❌ API 解析錯誤，請重試或聯繫工作人員: {e}"

        return False, "❌ API 回應異常，請重試或聯繫工作人員"

    finally:
        driver.quit()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
