// ==UserScript==
// @name         Quiz Assistant · Fill Only
// @namespace    quiz-assistant.local
// @version      0.1.0
// @description  Read visible question text and fill high-confidence local answers only.
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

(function () {
  'use strict'

  const apiUrl = localStorage.getItem('quiz_assistant_api') || 'http://127.0.0.1:8765'
  const session = localStorage.getItem('quiz_assistant_session') || 'local-session'

  function visibleText() {
    const selected = window.getSelection()?.toString().trim()
    return (selected || document.body.innerText || '').slice(0, 20000)
  }

  function extractOptions(text) {
    return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).flatMap((line) => {
      const match = line.match(/^([A-Ha-h])[.)、:：]\s*(.+)$/)
      return match ? [{ key: match[1].toUpperCase(), text: match[2].trim() }] : []
    })
  }

  function request(payload) {
    const body = JSON.stringify(payload)
    if (typeof GM_xmlhttpRequest === 'function') {
      return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
          method: 'POST',
          url: `${apiUrl}/api/queries`,
          headers: { 'Content-Type': 'application/json', 'X-Quiz-Session': session },
          data: body,
          onload: (response) => {
            if (response.status >= 200 && response.status < 300) resolve(JSON.parse(response.responseText))
            else reject(new Error(`本地 API 返回 ${response.status}`))
          },
          onerror: () => reject(new Error('无法连接本地 Quiz Assistant')),
        })
      })
    }
    return fetch(`${apiUrl}/api/queries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Quiz-Session': session },
      body,
    }).then((response) => {
      if (!response.ok) throw new Error(`本地 API 返回 ${response.status}`)
      return response.json()
    })
  }

  function findInput(key) {
    const inputs = [...document.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
    return inputs.find((input) => {
      const label = input.labels?.[0]?.innerText || input.getAttribute('aria-label') || ''
      return [input.value, label].some((value) => String(value || '').trim().toUpperCase().startsWith(key))
    })
  }

  async function fillOnly() {
    const text = visibleText()
    const options = extractOptions(text)
    const stem = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
      .filter((line) => !/^[A-Ha-h][.)、:：]\s+/.test(line)).slice(0, 8).join(' ')
    if (!stem || options.length < 2) throw new Error('请先选中包含题干和至少两个选项的题目区域')
    const result = await request({ text: stem, options: options.map((item) => `${item.key}. ${item.text}`), reveal: 'candidate' })
    if (!result.auto_answerable || !result.answer_keys?.length) {
      throw new Error(`本地匹配状态：${result.status}，不会填入`)
    }
    let filled = 0
    result.answer_keys.forEach((key) => {
      const input = findInput(key)
      if (!input) return
      input.checked = true
      input.dispatchEvent(new Event('input', { bubbles: true }))
      input.dispatchEvent(new Event('change', { bubbles: true }))
      filled += 1
    })
    if (!filled) throw new Error('找到答案，但当前页面没有匹配的选项控件')
    status.textContent = `已填入 ${result.answer_keys.join('、')}（${filled} 项）；请人工检查`
  }

  const button = document.createElement('button')
  button.type = 'button'
  button.textContent = 'Quiz Fill Only'
  button.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;padding:10px 14px;border:0;border-radius:8px;background:#29352d;color:#fff;cursor:pointer'
  const status = document.createElement('span')
  status.textContent = '仅填入模式'
  status.style.cssText = 'position:fixed;right:16px;bottom:60px;z-index:2147483647;padding:6px 9px;border-radius:6px;background:#fff;color:#29352d;font:12px sans-serif;box-shadow:0 2px 12px #0003'
  button.addEventListener('click', async () => {
    button.disabled = true
    try { await fillOnly() } catch (error) { status.textContent = error.message || '填入失败' }
    finally { button.disabled = false }
  })
  document.body.append(button, status)
}())
