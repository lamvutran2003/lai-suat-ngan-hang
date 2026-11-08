/* Hiện "Lượt xem" ở chân trang, lấy từ bộ đếm Cloudflare (counter/worker.js).
 * Phần tử: <p id="views" data-api="https://…workers.dev" data-site="tinhgium" data-base="/khoicai" hidden>…<b class="vp"></b>…<b class="vt"></b></p>
 * Mỗi trang chỉ cộng một lượt cho mỗi phiên trình duyệt (tải lại trang không cộng thêm). Không có data-api thì không làm gì.
 */
(function () {
  var el = document.getElementById("views");
  if (!el || !el.getAttribute("data-api") || !window.fetch) return;
  var base = el.getAttribute("data-base") || "", p = location.pathname.toLowerCase();
  if (base && p.indexOf(base) === 0) p = p.slice(base.length) || "/";
  p = p.replace(/index\.html$/, "");
  if (!/\/$/.test(p)) p += "/";
  var hit = 1, key = "tkd-view:" + p;
  try { if (sessionStorage.getItem(key)) hit = 0; sessionStorage.setItem(key, "1"); } catch (e) {}
  fetch(el.getAttribute("data-api").replace(/\/$/, "") + "/c?site=" + encodeURIComponent(el.getAttribute("data-site")) +
        "&p=" + encodeURIComponent(p) + "&hit=" + hit)
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (!d || typeof d.page !== "number") return;
      el.querySelector(".vp").textContent = d.page.toLocaleString("vi-VN");
      el.querySelector(".vt").textContent = d.total.toLocaleString("vi-VN");
      el.hidden = false;
    })["catch"](function () {});
})();
