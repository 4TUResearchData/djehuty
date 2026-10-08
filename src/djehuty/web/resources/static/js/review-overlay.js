/* Detached author-side review overlay for the dataset edit page.
 *
 * A static asset injected into /my/datasets/<id>/edit via a <script> tag, an
 * anchor div, and a stylesheet (the only legacy touches). It talks ONLY to the
 * /v3 review API with the author's own session cookie and renders nothing when
 * the feature is off (404/403) or there are no published comments. The author
 * sees published reviewer comments only -- never pending comments or internal
 * notes.
 *
 * One "Review" card lists every comment, headed by the field/entity it targets,
 * with a to-address/addressed status, replies, and bigger buttons. All styling
 * lives in /static/css/review-overlay.css (classes), because the app's CSP
 * forbids inline styles; the instance brand colour comes from the themed
 * corporate-identity-* classes the markup carries, and icons reuse the app's
 * Font Awesome set, so it feels native.
 */
(function () {
  "use strict";

  var FIELD_LABELS = {
    title: "Title", description: "Description", license_id: "Licence",
    license_remarks: "Licence remarks", group_id: "Group", categories: "Categories",
    references: "References", tags: "Keywords", defined_type: "Item type",
    resource_title: "Related resource title", resource_doi: "Related resource DOI",
    time_coverage: "Time coverage", data_link: "Data link", derived_from: "Derived from",
    same_as: "Same as", metadata_reason: "Metadata-only reason",
    author: "Author", funding: "Funding", category: "Category", file: "File",
    collaborator: "Collaborator"
  };

  var root = null, base = null, me = null;

  function api(method, path, body) {
    var opts = { method: method, credentials: "same-origin", headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts);
  }

  function el(tag, props, children) {
    var node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        if (k === "text") { node.textContent = props[k]; }
        else if (k === "class") { node.className = props[k]; }
        else { node.setAttribute(k, props[k]); }
      });
    }
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function icon(faClass, extra) {
    return el("span", { class: faClass + (extra ? " " + extra : ""), "aria-hidden": "true" });
  }

  function btn(text, cls, faClass, onClick) {
    var b = el("button", { type: "button", class: cls });
    if (faClass) { b.appendChild(icon(faClass)); }
    b.appendChild(document.createTextNode(text));
    b.addEventListener("click", onClick);
    return b;
  }

  function prettify(token) {
    if (!token) { return ""; }
    return token.replace(/_/g, " ").replace(/^./, function (c) { return c.toUpperCase(); });
  }

  function label(comment) {
    if (comment.target_label) { return comment.target_label; }
    if (comment.target_type === "scalar") {
      return FIELD_LABELS[comment.target_key] || prettify(comment.target_key);
    }
    return FIELD_LABELS[comment.target_type] || prettify(comment.target_type);
  }

  // -- modal ----------------------------------------------------------------

  function openModal(title, initialText, onSave) {
    var textarea = el("textarea", { placeholder: "Write your reply…" });
    textarea.value = initialText || "";
    var backdrop = el("div", { class: "ro-modal-backdrop" });
    function close() { document.body.removeChild(backdrop); }
    backdrop.appendChild(el("div", { class: "ro-modal" }, [
      el("h3", { text: title }),
      textarea,
      el("div", { class: "ro-modal-actions" }, [
        btn("Cancel", "ro-btn", "fas fa-xmark", close),
        btn("Save", "ro-cta corporate-identity-standard-button", "fas fa-check", function () {
          var v = textarea.value.trim();
          if (v) { onSave(v, close); }
        })
      ])
    ]));
    backdrop.addEventListener("click", function (e) { if (e.target === backdrop) { close(); } });
    document.body.appendChild(backdrop);
    textarea.focus();
  }

  // -- rendering ------------------------------------------------------------

  function renderReplies(comment) {
    var wrap = el("div");
    (comment.events || []).forEach(function (ev) {
      if (ev.kind !== "reply") { return; }
      var who = ev.account_uuid === comment.created_by_account_uuid ? "Reviewer" : "You";
      var line = el("div", { class: "ro-event" }, [
        el("span", { class: "ro-who", text: who + ": " }),
        el("span", { text: ev.body || "" })
      ]);
      if (ev.account_uuid === me) {
        line.appendChild(document.createTextNode("  "));
        line.appendChild(btn("Edit", "ro-sbtn", "fas fa-pen", function () {
          openModal("Edit reply", ev.body, function (v, close) {
            api("PATCH", base + "/comments/" + comment.id + "/replies/" + ev.id, { body: v })
              .then(function () { close(); reload(); });
          });
        }));
        line.appendChild(btn("Delete", "ro-sbtn", "fas fa-trash-can", function () {
          if (!window.confirm("Delete this reply?")) { return; }
          api("DELETE", base + "/comments/" + comment.id + "/replies/" + ev.id).then(reload);
        }));
      }
      wrap.appendChild(line);
    });
    return wrap;
  }

  function widget(comment) {
    var done = !!comment.author_addressed;
    // Addressed comments collapse to just their header; "to address" stay open.
    var box = el("div", { class: "ro-card" + (done ? " ro-card-done ro-collapsed" : "") });

    var status = done
      ? el("span", { class: "ro-pill ro-pill-done" }, [icon("fas fa-circle-check"), document.createTextNode("Addressed")])
      : el("span", { class: "ro-pill ro-pill-todo" }, [icon("fas fa-circle-exclamation"), document.createTextNode("To address")]);
    var right = el("div", { class: "ro-head-right" }, [status]);
    if (done) { right.appendChild(icon("fas fa-chevron-down", "ro-chevron")); }

    var head = el("div", { class: "ro-card-head" + (done ? " ro-toggle" : "") }, [
      el("span", { class: "ro-chip", text: label(comment) }),
      right
    ]);
    if (done) {
      head.setAttribute("title", "Show comment");
      head.addEventListener("click", function () { box.classList.toggle("ro-collapsed"); });
    }
    box.appendChild(head);

    var details = el("div", { class: "ro-details" });
    if (comment.field_value_snapshot != null) {
      details.appendChild(el("div", { class: "ro-snapshot", text: "At review: " + comment.field_value_snapshot }));
    }
    details.appendChild(el("div", { class: "ro-text", text: comment.body || "" }));
    if (comment.updated_at) { details.appendChild(el("div", { class: "ro-edited", text: "(edited)" })); }
    details.appendChild(renderReplies(comment));

    details.appendChild(el("div", { class: "ro-actions" }, [
      btn("Reply", "ro-btn", "fas fa-reply", function () {
        openModal("Reply to the reviewer", "", function (v, close) {
          api("POST", base + "/comments/" + comment.id + "/replies", { body: v })
            .then(function () { close(); reload(); });
        });
      }),
      btn(done ? "Mark not addressed" : "Mark as addressed", "ro-btn",
        done ? "fas fa-rotate-left" : "fas fa-check", function () {
          api("POST", base + "/comments/" + comment.id + "/addressed", { addressed: !done }).then(reload);
        })
    ]));
    box.appendChild(details);
    return box;
  }

  function render(convo) {
    root.textContent = "";
    var comments = convo.comments || [];
    var rounds = convo.rounds || [];
    var generalNotes = rounds.length ? rounds[rounds.length - 1].general_notes : null;
    if (!comments.length && !generalNotes) { return; }

    var total = comments.length;
    var done = comments.filter(function (c) { return c.author_addressed; }).length;
    var allDone = total > 0 && done === total;

    var progress = el("span", {
      class: allDone ? "ro-progress ro-done" : "ro-progress corporate-identity-background"
    }, [
      icon(allDone ? "fas fa-circle-check" : "fas fa-list-check"),
      document.createTextNode(done + " of " + total + " addressed")
    ]);

    var header = el("div", { class: "ro-head" }, [
      el("div", { class: "ro-head-top" }, [
        el("div", { class: "ro-title" }, [
          icon("fas fa-comments", "ro-ico corporate-identity"),
          document.createTextNode("Changes requested by the reviewer")
        ]),
        total ? progress : el("span")
      ]),
      el("div", { class: "ro-subtitle", text: "Please address the comments below, then let the reviewer know you're done." })
    ]);

    var bodyWrap = el("div", { class: "ro-body" });
    if (generalNotes) {
      bodyWrap.appendChild(el("div", { class: "ro-note" }, [
        el("div", { class: "ro-note-label", text: "General note" }),
        el("div", { text: generalNotes })
      ]));
    }
    comments.forEach(function (c) { bodyWrap.appendChild(widget(c)); });

    var cta = btn("I've addressed the comments — notify the reviewer",
      "ro-cta corporate-identity-standard-button", "fas fa-paper-plane", function () {
        api("POST", base + "/send-back").then(function (resp) {
          window.alert(resp.ok ? "The reviewer has been notified." : "Could not notify the reviewer.");
        });
      });
    var footer = el("div", { class: "ro-foot" }, [cta]);

    root.appendChild(el("div", { class: "ro-panel corporate-identity-header" }, [header, bodyWrap, footer]));
  }

  function reload() {
    api("GET", base).then(function (resp) {
      if (!resp.ok) { root.textContent = ""; return; }
      resp.json().then(render);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    root = document.getElementById("review-overlay-root");
    if (!root) { return; }
    var uuid = root.getAttribute("data-dataset-uuid");
    if (!uuid) { return; }
    me = root.getAttribute("data-account-uuid");
    base = "/v3/datasets/" + encodeURIComponent(uuid) + "/review";
    reload();
  });
})();
