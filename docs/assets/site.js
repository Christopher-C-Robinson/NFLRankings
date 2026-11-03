/* Root-absolute URLs for GitHub project Pages.
   Live site: https://christopher-c-robinson.github.io/NFLRankings/
   Without a trailing slash, relative "assets/..." and "data/..." resolve on
   the host root, so the stylesheet and scripts never run. */
(function (root) {
  "use strict";
  var ROOT = "/NFLRankings/";
  var TIMEOUT_MS = 8000;

  function page(file) {
    return ROOT + String(file || "").replace(/^\//, "");
  }

  function data(name) {
    return ROOT + "data/" + String(name || "").replace(/^\//, "");
  }

  function $(id) {
    return document.getElementById(id);
  }

  function setText(id, text) {
    var el = $(id);
    if (el) el.textContent = text;
    return el;
  }

  function getJSON(url) {
    return new Promise(function (resolve, reject) {
      var settled = false;
      var ctrl = typeof AbortController === "function" ? new AbortController() : null;
      function finish(fn, value) {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        fn(value);
      }
      var timer = setTimeout(function () {
        if (ctrl) ctrl.abort();
        finish(reject, new Error("timed out after 8s"));
      }, TIMEOUT_MS);
      var opts = { cache: "no-cache" };
      if (ctrl) opts.signal = ctrl.signal;
      fetch(url, opts).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      }).then(function (body) {
        finish(resolve, body);
      }, function (err) {
        if (err && err.name === "AbortError") finish(reject, new Error("timed out after 8s"));
        else finish(reject, err instanceof Error ? err : new Error(String(err)));
      });
    });
  }

  root.NFLSite = { ROOT: ROOT, page: page, data: data, $: $, setText: setText, getJSON: getJSON };
})(window);
