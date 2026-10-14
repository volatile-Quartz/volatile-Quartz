// Last.fm 周报页提取器（固化版）：只做一件事，返回页面全量可视文本。
// 每周抓页时在浏览器 console / browser_evaluate 中执行，返回值保存为纯文本，
// 交给 listening_report_pull.py --page-text 本地解析。
// 页面地址：https://www.last.fm/user/<user>/listening-report/week
(function () {
  var t = document.body.innerText;
  if (t.length > 200000) t = t.slice(0, 200000);
  return t;
})()
