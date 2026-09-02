import { expect, test } from '@playwright/test'

test('user can search and complete a practice question without answer leakage', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByText('Quiz Assistant', { exact: true })).toBeVisible()
  await expect(page.getByText('english-basic')).toBeVisible()

  await page.getByRole('link', { name: '查询答案' }).click()
  await page.getByLabel('题干').fill('Which sentence is grammatically correct?')
  await page.getByRole('button', { name: '查询' }).click()
  await expect(page.getByText('He goes to school.')).toBeVisible()
  await expect(page.getByText('高置信度候选')).toBeVisible()

  await page.getByRole('link', { name: '开始练习' }).first().click()
  await expect(page.getByText('Which sentence is grammatically correct?')).toBeVisible()
  await expect(page.getByText('第三人称单数主语 He 后使用 goes。')).not.toBeVisible()

  await page.getByRole('button', { name: '本地自动匹配' }).click()
  await expect(page.getByText('已填入本地题库的高置信度答案；请检查后再提交。')).toBeVisible()
  await expect(page.getByRole('radio', { name: /He goes to school/ })).toBeChecked()
  await page.getByRole('button', { name: '提交答案' }).click()
  await expect(page.getByText('回答正确')).toBeVisible()
  await expect(page.getByText('第三人称单数主语 He 后使用 goes。')).toBeVisible()
})
