import os
import time
import pycurl
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Log


# how to install the geckodrivers
# https://github.com/SergeyPirogov/webdriver_manager
# from webdriver_manager.firefox import GeckoDriverManager
# GeckoDriverManager().install()

USERNAME = 'test'
PASSWORD = '1234'

def get_keycloak_url():
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, 'http://localhost:8000/login')
    c.setopt(c.FOLLOWLOCATION, True)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    
    return buffer.getvalue().decode('utf-8')

log=Log()
def driver():
    log.level = "TRACE"
    options = Options()
    options.add_argument("--headless")
    options.add_argument(log.level)

    # options.add_argument('--no-sandbox')
    # options.add_argument('--disable-dev-shm-usage')

    executable_path = os.path.expanduser(
        "~/.wdm/drivers/geckodriver/linux64/v0.34.0/geckodriver"
    )
    service = Service(
        executable_path=executable_path,
        log_output="geckodriver.log"
    )

    driver = webdriver.Firefox(
        options=options, 
        service=service,
    )
    driver.set_window_size(1920, 1080)
    driver.maximize_window()
    driver.implicitly_wait(10)
    return driver

driver = driver()
try:
    keycloak_url = get_keycloak_url()
    driver.get(keycloak_url)

    print(driver.title)
    username_box = driver.find_element(By.ID, "username")
    print("username_box", username_box.get_attribute("outerHTML"))
    username_box.send_keys(USERNAME)
    
    password_box = driver.find_element(By.ID, "password")
    print("password_box", password_box.get_attribute("outerHTML"))
    password_box.send_keys(PASSWORD)
    password_box.send_keys(Keys.RETURN)
    print("---TOKEN---")
    
    time.sleep(1)
    if "Sign in" in driver.title:
       raise Exception("Failed to login")
    
    token=driver.find_element(By.TAG_NAME, "body").text
    if token == "":
        raise Exception("Failed to get token")
    
    print(token)
    with open("kc.env", "w") as f:
        f.write(f"TOKEN={token}")

except Exception as e:
    print(e)
    
finally:
    driver.quit()
