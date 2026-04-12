"""
LinkedIn Jobs search + Easy Apply automation.

LinkedIn changes markup often; selectors are best-effort with fallbacks.
Use only on accounts you own and respect site terms and rate limits.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus, urlparse

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from config import JOB_APPLICATIONS_DIR, JOB_MAX_APPLICATIONS, MINIMUM_WAIT_TIME_IN_SECONDS
from src.job import Job
from src.job_application import JobApplication
from src.job_application_saver import ApplicationSaver
from src.libs.llm_manager import GPTAnswerer
from src.logging import logger


def _norm_job_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("/"):
        href = "https://www.linkedin.com" + href
    p = urlparse(href)
    path = p.path.split("?")[0]
    return f"{p.scheme or 'https'}://{p.netloc or 'www.linkedin.com'}{path}".rstrip("/")


def build_linkedin_search_url(prefs: Dict[str, Any]) -> str:
    positions = prefs.get("positions") or ["Software Engineer"]
    locations = prefs.get("locations") or [""]
    keywords = " OR ".join(str(p) for p in positions)
    location = str(locations[0]) if locations else ""
    params: List[str] = [
        f"keywords={quote_plus(keywords)}",
        f"location={quote_plus(location)}",
    ]
    date = prefs.get("date") or {}
    if date.get("24_hours"):
        params.append("f_TPR=r86400")
    elif date.get("week"):
        params.append("f_TPR=r604800")
    elif date.get("month"):
        params.append("f_TPR=r2592000")
    wt: List[str] = []
    if prefs.get("remote"):
        wt.append("2")
    if prefs.get("onsite"):
        wt.append("1")
    if prefs.get("hybrid"):
        wt.append("3")
    if wt:
        params.append("f_WT=" + "%2C".join(wt))
    return "https://www.linkedin.com/jobs/search/?" + "&".join(params)


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"urls": [], "companies": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("urls", [])
        data.setdefault("companies", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"urls": [], "companies": []}


def _save_state(path: Path, urls: Set[str], companies: Set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"urls": sorted(urls), "companies": sorted(companies)},
            f,
            indent=2,
        )


class LinkedInEasyApplier:
    def __init__(
        self,
        driver: WebDriver,
        gpt: GPTAnswerer,
        work_preferences: Dict[str, Any],
        state_path: Path,
        resume_pdf_path: Optional[str] = None,
    ):
        self.driver = driver
        self.gpt = gpt
        self.prefs = work_preferences
        self.state_path = state_path
        self.resume_pdf_path = resume_pdf_path
        st = _load_state(state_path)
        self._applied_urls: Set[str] = set(st["urls"])
        self._applied_companies: Set[str] = {c.lower() for c in st["companies"]}
        self.apply_once = bool(work_preferences.get("apply_once_at_company", True))
        self.company_blacklist = {b.lower() for b in (work_preferences.get("company_blacklist") or [])}
        self.title_blacklist = {b.lower() for b in (work_preferences.get("title_blacklist") or [])}

    def _blacklisted(self, title: str, company: str) -> bool:
        t, c = title.lower(), company.lower()
        if any(b in c for b in self.company_blacklist):
            return True
        if any(b in t for b in self.title_blacklist):
            return True
        return False

    def wait_manual_login(self) -> None:
        self.driver.get("https://www.linkedin.com/feed/")
        logger.info(
            "Sign in to LinkedIn in the browser window if needed, then return here."
        )
        input("Press Enter after you are logged in and the feed loads… ")

    def collect_job_links(self, limit: int = 40) -> List[str]:
        for _ in range(4):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
        seen: Set[str] = set()
        links: List[str] = []
        selectors = [
            "a[href*='/jobs/view/']",
            "div.job-card-container a.job-card-container__link",
            "a.job-card-list__title",
        ]
        for sel in selectors:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    href = el.get_attribute("href") or ""
                    u = _norm_job_url(href)
                    if "/jobs/view/" in u and u not in seen:
                        seen.add(u)
                        links.append(u)
                        if len(links) >= limit:
                            return links
            except StaleElementReferenceException:
                continue
        return links

    def _read_job_page(self) -> Job:
        job = Job(link=self.driver.current_url)
        time.sleep(1.5)
        title = ""
        company = ""
        location = ""
        desc = ""
        try:
            for sel in [
                "h1.t-24",
                "h1.job-title",
                "h1[class*='job-title']",
            ]:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    title = els[0].text.strip()
                    break
        except NoSuchElementException:
            pass
        try:
            for sel in [
                "a.job-details-j4eu-wyd",
                "div.job-details-jupiter-apollo a",
                "div[data-test-job-details-header] a",
            ]:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    company = els[0].text.strip()
                    break
        except NoSuchElementException:
            pass
        try:
            els = self.driver.find_elements(
                By.CSS_SELECTOR,
                "span.job-details-jupiter-apollo__subtitle, .job-details-jupiter-apollo__subtitle",
            )
            if els:
                location = els[0].text.strip()
        except NoSuchElementException:
            pass
        try:
            els = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div.jobs-description-content__text, article.jobs-description__container, #job-details",
            )
            if els:
                desc = els[0].text.strip()
        except NoSuchElementException:
            pass
        job.role = title or "Unknown title"
        job.company = company or "Unknown company"
        job.location = location
        job.description = desc
        job.apply_method = "linkedin_easy_apply"
        return job

    def _find_easy_apply(self):
        xpaths = [
            "//button[contains(@class,'jobs-apply-button')]",
            "//button[contains(., 'Easy Apply')]",
            "//div[contains(@class,'jobs-s-apply')]//button",
        ]
        for xp in xpaths:
            els = self.driver.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed() and el.is_enabled():
                    return el
        return None

    def _modal_root(self):
        sels = [
            "div[data-test-modal-container]",
            "div.artdeco-modal",
            "div[role='dialog']",
        ]
        for s in sels:
            els = self.driver.find_elements(By.CSS_SELECTOR, s)
            for el in els:
                if el.is_displayed():
                    return el
        return None

    def _answer_for_label(self, question: str) -> str:
        q = (question or "Application question").strip()[:2000]
        return self.gpt.answer_question_textual_wide_range(q)

    def _fill_text_fields(self, modal) -> int:
        count = 0
        for el in modal.find_elements(By.CSS_SELECTOR, "textarea, input[type='text']"):
            try:
                if not el.is_displayed() or not el.is_enabled():
                    continue
                name = el.get_attribute("aria-label") or el.get_attribute("placeholder") or "Question"
                if el.get_attribute("value"):
                    continue
                ans = self._answer_for_label(name)
                el.clear()
                el.send_keys(ans[:4000])
                count += 1
            except StaleElementReferenceException:
                continue
        return count

    def _fill_selects(self, modal) -> int:
        count = 0
        for el in modal.find_elements(By.TAG_NAME, "select"):
            try:
                if not el.is_displayed():
                    continue
                sel = Select(el)
                opts = [o.text.strip() for o in sel.options if o.text.strip()]
                if len(opts) < 2:
                    continue
                label = el.get_attribute("aria-label") or "Select option"
                choice = self.gpt.answer_question_from_options(label, opts)
                pick = GPTAnswerer.find_best_match(choice, opts)
                try:
                    sel.select_by_visible_text(pick)
                except Exception:
                    if opts:
                        sel.select_by_index(1)
                count += 1
            except StaleElementReferenceException:
                continue
        return count

    def _fill_radios(self, modal) -> int:
        count = 0
        groups = modal.find_elements(By.CSS_SELECTOR, "fieldset, div[data-test-form-builder-radio-button-form-component]")
        for group in groups:
            try:
                radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if len(radios) < 2:
                    continue
                labels = []
                for r in radios:
                    rid = r.get_attribute("id")
                    text = ""
                    if rid:
                        labs = group.find_elements(By.CSS_SELECTOR, f"label[for='{rid}']")
                        if labs:
                            text = labs[0].text.strip()
                    labels.append(text or "Option")
                legend_el = group.find_elements(By.TAG_NAME, "legend")
                q = legend_el[0].text.strip() if legend_el else "Choose one option"
                choice = self.gpt.answer_question_from_options(q, labels)
                pick = GPTAnswerer.find_best_match(choice, labels)
                for i, lab in enumerate(labels):
                    if lab == pick and i < len(radios):
                        radios[i].click()
                        count += 1
                        break
            except StaleElementReferenceException:
                continue
        return count

    def _upload_resume_if_needed(self, modal) -> None:
        if not self.resume_pdf_path or not os.path.isfile(self.resume_pdf_path):
            return
        path = os.path.abspath(self.resume_pdf_path)
        for inp in modal.find_elements(By.CSS_SELECTOR, "input[type='file']"):
            try:
                if inp.is_displayed() or True:
                    inp.send_keys(path)
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _click_footer_button(self, texts: tuple) -> bool:
        for text in texts:
            try:
                xp = f"//button[contains(., '{text}')]"
                els = self.driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed() and el.is_enabled():
                        el.click()
                        time.sleep(1.2)
                        return True
            except Exception:
                continue
        return False

    def _run_modal_steps(self) -> bool:
        for step in range(18):
            modal = self._modal_root()
            if not modal:
                body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "application sent" in body or "submitted" in body:
                    return True
                time.sleep(1)
                continue
            self._upload_resume_if_needed(modal)
            self._fill_selects(modal)
            self._fill_radios(modal)
            self._fill_text_fields(modal)
            if self._click_footer_button(("Submit application", "Submit", "Done")):
                time.sleep(2)
                body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "application sent" in body or "your application was sent" in body:
                    return True
                return True
            if self._click_footer_button(("Next", "Continue", "Review")):
                time.sleep(MINIMUM_WAIT_TIME_IN_SECONDS / 6)
                continue
            if self._click_footer_button(("Dismiss",)):
                return False
            time.sleep(1.5)
        return False

    def apply_to_job_url(self, url: str) -> bool:
        if url in self._applied_urls:
            return False
        self.driver.get(url)
        job = self._read_job_page()
        self.gpt.set_job(job)
        if self._blacklisted(job.role, job.company):
            logger.info(f"Skip blacklisted: {job.company} — {job.role}")
            return False
        if self.apply_once and job.company.lower() in self._applied_companies:
            logger.info(f"Skip duplicate company: {job.company}")
            return False
        if not self.gpt.is_job_suitable():
            logger.info(f"Skip low-fit job: {job.role}")
            return False
        btn = self._find_easy_apply()
        if not btn:
            logger.info(f"No Easy Apply: {job.role} @ {job.company}")
            return False
        try:
            btn.click()
        except Exception as e:
            logger.warning(f"Could not click Easy Apply: {e}")
            return False
        time.sleep(2)
        ok = self._run_modal_steps()
        if ok:
            self._applied_urls.add(_norm_job_url(url))
            self._applied_companies.add(job.company.lower())
            _save_state(self.state_path, self._applied_urls, self._applied_companies)
            ja = JobApplication(job=job, application={"status": "submitted", "url": url})
            if self.resume_pdf_path:
                ja.resume_path = self.resume_pdf_path
                job.resume_path = self.resume_pdf_path
            os.makedirs(JOB_APPLICATIONS_DIR, exist_ok=True)
            try:
                ApplicationSaver.save(ja)
            except Exception as e:
                logger.warning(f"Could not save application folder: {e}")
            logger.info(f"Applied: {job.role} @ {job.company}")
        return ok

    def run_search_loop(self, max_applications: Optional[int] = None) -> None:
        cap = max_applications if max_applications is not None else JOB_MAX_APPLICATIONS
        url = build_linkedin_search_url(self.prefs)
        logger.info(f"Opening search: {url}")
        self.driver.get(url)
        time.sleep(3)
        links = self.collect_job_links(limit=60)
        logger.info(f"Found {len(links)} job links.")
        submitted = 0
        for link in links:
            if submitted >= cap:
                break
            try:
                if self.apply_to_job_url(link):
                    submitted += 1
                    logger.info(f"Submitted {submitted}/{cap}")
                    time.sleep(MINIMUM_WAIT_TIME_IN_SECONDS)
            except Exception as e:
                logger.exception(f"Error on {link}: {e}")
                continue
