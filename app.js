(function () {
  "use strict";

  var TORONTO = { lat: 43.6532, lon: -79.3832, tz: "America/Toronto" };

  var KIND_LABEL = {
    lyric:    "lyric",
    dialogue: "dialogue",
    quote:    "quote",
    passage:  "passage"
  };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function join(parts, sep) {
    return parts.filter(function (p) { return p; }).join(sep || ", ");
  }

  // Only https links may become clickable. Source URLs arrive from third-party
  // APIs, and a javascript: or data: URL would otherwise run on click.
  function safeUrl(value) {
    try {
      var u = new URL(value);
      return u.protocol === "https:" ? u.href : null;
    } catch (e) {
      return null;
    }
  }

  /* ---------------------------------------------------------- entry */

  function metaRows(item) {
    var x = item.expansion;
    var meta = (x && x.meta) || {};
    var rows = [];

    if (item.type === "lyric") {
      rows.push(["Song", item.source || meta.title]);
      rows.push(["Album", item.source && meta.album && meta.album !== item.source ? meta.album : null]);
      rows.push(["Released", meta.released || item.year]);
      rows.push(["Produced", join(meta.producers)]);
      rows.push(["Written", join(meta.writers)]);
    } else if (item.type === "dialogue") {
      rows.push([meta.title ? "Title" : null, meta.title || item.source]);
      rows.push(["Released", meta.released || item.year]);
      rows.push([meta.lead_label || "Directed by", join(meta.leads)]);
      rows.push(["Genre", join(meta.genres)]);
    } else if (item.type === "quote") {
      rows.push(["Source", item.source]);
      rows.push(["Year", item.year]);
      rows.push(["Known for", meta.subtitle]);
    } else if (item.type === "passage") {
      rows.push(["Book", meta.title || item.source]);
      rows.push(["Author", join(meta.authors) || item.attribution]);
      rows.push(["Published", meta.published || item.year]);
      rows.push(["Subjects", join(meta.subjects)]);
    } else {
      rows.push(["Source", item.source]);
      rows.push(["Year", item.year]);
    }

    return rows.filter(function (r) { return r[0] && r[1]; });
  }

  function render(item) {
    var main = document.getElementById("entry");
    main.textContent = "";

    main.appendChild(el("h1", "headword", item.text));

    var grammar = el("p", "grammar");
    var kind = KIND_LABEL[item.type];
    if (kind) grammar.appendChild(el("span", "kind", kind + "."));
    if (item.attribution) {
      grammar.appendChild(document.createTextNode(item.attribution));
    }
    if (grammar.childNodes.length) main.appendChild(grammar);

    // Sourced context first, then your own note as its own paragraph.
    var body = (item.expansion && item.expansion.body) || [];

    if (body.length || item.note) {
      var block = el("div", "senses");
      body.forEach(function (para) { block.appendChild(el("p", null, para)); });
      if (item.note) block.appendChild(el("p", "own", item.note));
      main.appendChild(block);
    }

    var rows = metaRows(item);
    if (rows.length) {
      var list = el("ul", "facts");
      rows.forEach(function (row) {
        var li = el("li");
        li.appendChild(el("span", "label", row[0]));
        li.appendChild(el("span", "value", String(row[1])));
        list.appendChild(li);
      });
      main.appendChild(list);
    }

    // Data credits share one line: "Context from X. Weather from Open-Meteo."
    var href = item.expansion && safeUrl(item.expansion.source_url);
    if (href) {
      var line = document.getElementById("sourceline");
      line.textContent = "Context from ";
      var a = el("a", null, item.expansion.source_name || "source");
      a.href = href;
      a.rel = "noopener";
      line.appendChild(a);
      line.appendChild(document.createTextNode(". "));
    }

    // TMDB's terms require this wording whenever their data is shown.
    if (item.type === "dialogue" && item.expansion) {
      document.getElementById("tmdb-notice").textContent =
        " This product uses the TMDB API but is not endorsed or certified by TMDB.";
    }
  }

  function failed() {
    var main = document.getElementById("entry");
    main.textContent = "";
    main.appendChild(el("p", "bare", "Today's entry could not be loaded."));
  }

  /* --------------------------------------------------------- footer */

  function dateline() {
    return new Date().toLocaleDateString("en-CA", {
      timeZone: TORONTO.tz,
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    });
  }

  function paintFooterLine(temp) {
    var node = document.getElementById("dateline");
    node.textContent = dateline();
    if (temp === undefined || temp === null) return;

    node.appendChild(el("span", "sep", "\u00B7"));
    node.appendChild(
      document.createTextNode("Toronto, " + Math.round(temp) + "\u00B0C")
    );
  }

  function weather() {
    var url = "https://api.open-meteo.com/v1/forecast"
      + "?latitude=" + TORONTO.lat
      + "&longitude=" + TORONTO.lon
      + "&current=temperature_2m"
      + "&timezone=" + encodeURIComponent(TORONTO.tz);

    fetch(url)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        var t = data && data.current && data.current.temperature_2m;
        paintFooterLine(t);
      })
      .catch(function () { /* date alone, already painted */ });
  }

  /* ----------------------------------------------------------- boot */

  paintFooterLine(null);
  weather();

  fetch("item.json?v=" + Date.now())
    .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
    .then(render)
    .catch(failed);
})();