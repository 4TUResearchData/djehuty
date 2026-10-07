/* Read-only field-level review page for reviewers.
 *
 * Shows every field the author edits -- scalar fields and entity/section fields
 * (authors, categories, funding, files, collaborators, references, keywords) --
 * read-only, each with its reviewer comments. A comment is a single editable
 * body (add/edit via a modal, not a reply thread), with Delete and Resolve;
 * author replies appear beneath, labelled by role. Talks only to the /v3
 * conversation API with the reviewer's own session cookie.
 */
(function () {
  "use strict";

  var ctx = window.reviewContext || { datasetUuid: null, authorUuid: null, fields: [], entities: [] };
  var BASE = "/v3/datasets/" + encodeURIComponent(ctx.datasetUuid) + "/review";

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
      Object.keys(props).forEach(function (key) {
        if (key === "class") { node.className = props[key]; }
        else if (key === "text") { node.textContent = props[key]; }
        else { node.setAttribute(key, props[key]); }
      });
    }
    (children || []).forEach(function (child) { node.appendChild(child); });
    return node;
  }

  function button(text, onClick) {
    var b = el("button", { type: "button", text: text });
    b.addEventListener("click", onClick);
    return b;
  }

  // -- modal ----------------------------------------------------------------

  function openModal(title, initialText, onSave) {
    var textarea = el("textarea", { placeholder: "Write your comment…" });
    textarea.value = initialText || "";
    var backdrop = el("div", { class: "review-modal-backdrop" });
    function close() { document.body.removeChild(backdrop); }
    var modal = el("div", { class: "review-modal" }, [
      el("h3", { text: title }),
      textarea,
      el("div", { class: "review-modal-actions" }, [
        button("Cancel", close),
        button("Save", function () {
          var value = textarea.value.trim();
          if (!value) { return; }
          onSave(value, close);
        })
      ])
    ]);
    backdrop.appendChild(modal);
    backdrop.addEventListener("click", function (event) {
      if (event.target === backdrop) { close(); }
    });
    document.body.appendChild(backdrop);
    textarea.focus();
  }

  // -- comments -------------------------------------------------------------

  function roleOf(accountUuid) {
    return accountUuid === ctx.authorUuid ? "Author" : "Reviewer";
  }

  function commentsFor(convo, targetType, targetKey) {
    return (convo.comments || []).filter(function (c) {
      return c.target_type === targetType && (c.target_key || null) === (targetKey || null);
    });
  }

  function renderReplies(comment) {
    var wrap = el("div");
    (comment.events || []).forEach(function (event) {
      if (event.kind === "reply") {
        wrap.appendChild(el("div", { class: "review-event" }, [
          el("span", { class: "who", text: roleOf(event.account_uuid) + ": " }),
          el("span", { text: event.body || "" })
        ]));
      }
    });
    return wrap;
  }

  function renderComment(comment) {
    var box = el("div", { class: "review-comment" + (comment.reviewer_resolved ? " resolved" : "") });
    if (comment.field_value_snapshot != null) {
      box.appendChild(el("div", { class: "review-snapshot", text: "At comment time: " + comment.field_value_snapshot }));
    }
    box.appendChild(el("div", { class: "body", text: comment.body || "" }));
    if (comment.updated_at) { box.appendChild(el("div", { class: "edited", text: "(edited)" })); }
    box.appendChild(renderReplies(comment));
    box.appendChild(el("div", {}, [
      button("Edit", function () {
        openModal("Edit comment", comment.body, function (value, close) {
          api("PATCH", BASE + "/comments/" + comment.id, { body: value }).then(function () { close(); reload(); });
        });
      }),
      button("Delete", function () {
        if (!window.confirm("Delete this comment?")) { return; }
        api("DELETE", BASE + "/comments/" + comment.id).then(reload);
      }),
      button(comment.reviewer_resolved ? "Reopen" : "Resolve", function () {
        api("POST", BASE + "/comments/" + comment.id + "/resolve",
            { resolved: !comment.reviewer_resolved }).then(reload);
      })
    ]));
    return box;
  }

  function addCommentButton(targetType, targetKey, label) {
    return el("div", { class: "review-add" }, [
      button("+ Add comment", function () {
        openModal("Comment on " + label, "", function (text, close) {
          api("POST", BASE + "/comments",
              { target_type: targetType, target_key: targetKey, target_label: label, body: text })
            .then(function () { close(); reload(); });
        });
      })
    ]);
  }

  function attachComments(block, convo, targetType, targetKey, label) {
    commentsFor(convo, targetType, targetKey).forEach(function (comment) {
      block.appendChild(renderComment(comment));
    });
    block.appendChild(addCommentButton(targetType, targetKey, label));
  }

  // -- field / entity rendering --------------------------------------------

  function renderField(convo, field) {
    var block = el("div", { class: "review-field" });
    block.appendChild(el("h3", { text: field.label }));
    block.appendChild(field.value && field.value.length
      ? el("div", { class: "value", text: field.value })
      : el("div", { class: "value empty", text: "(empty)" }));
    attachComments(block, convo, "scalar", field.token, field.label);
    return block;
  }

  function renderEntitySection(convo, section) {
    var block = el("div", { class: "review-field" });
    block.appendChild(el("h3", { text: section.label }));

    if (section.section) {
      // Section-level (references, keywords): list values read-only, one thread.
      if (section.items.length) {
        var list = el("ul");
        section.items.forEach(function (item) { list.appendChild(el("li", { text: item.label })); });
        block.appendChild(list);
      } else {
        block.appendChild(el("div", { class: "value empty", text: "(empty)" }));
      }
      attachComments(block, convo, section.target_type, null, section.label);
      return block;
    }

    if (!section.items.length) {
      block.appendChild(el("div", { class: "value empty", text: "(empty)" }));
      return block;
    }
    section.items.forEach(function (item) {
      var row = el("div", { class: "review-entity-item" });
      row.appendChild(el("div", { class: "entity-label", text: item.label }));
      if (item.details && item.details.length) {
        var dl = el("dl", { class: "review-details" });
        item.details.forEach(function (d) {
          dl.appendChild(el("dt", { text: d.label }));
          dl.appendChild(el("dd", { text: d.value }));
        });
        row.appendChild(dl);
      }
      attachComments(row, convo, section.target_type, item.key, section.label + ": " + item.label);
      block.appendChild(row);
    });
    return block;
  }

  // -- other / notes / actions ----------------------------------------------

  function anchoredKey(targetType, targetKey) { return targetType + "::" + (targetKey || ""); }

  function renderUnanchored(convo) {
    var anchored = {};
    (ctx.fields || []).forEach(function (f) { anchored[anchoredKey("scalar", f.token)] = true; });
    (ctx.entities || []).forEach(function (s) {
      if (s.section) { anchored[anchoredKey(s.target_type, null)] = true; }
      else { s.items.forEach(function (item) { anchored[anchoredKey(s.target_type, item.key)] = true; }); }
    });
    var others = (convo.comments || []).filter(function (c) {
      return !anchored[anchoredKey(c.target_type, c.target_key)];
    });
    if (!others.length) { return null; }
    var block = el("div", { class: "review-field" });
    block.appendChild(el("h3", { text: "Other comments" }));
    others.forEach(function (comment) {
      block.appendChild(el("div", { class: "review-snapshot",
        text: comment.target_type + (comment.target_key ? " · " + comment.target_key : "") }));
      block.appendChild(renderComment(comment));
    });
    return block;
  }

  function latestRound(convo) {
    var rounds = convo.rounds || [];
    return rounds.length ? rounds[rounds.length - 1] : {};
  }

  function renderNotes(convo) {
    var round = latestRound(convo);
    var block = el("div", { class: "review-notes review-field" });
    block.appendChild(el("h3", { text: "Notes" }));
    var general = el("textarea", { placeholder: "General notes (shared with the author on submit)" });
    general.value = round.general_notes || "";
    var internal = el("textarea", { placeholder: "Internal notes (reviewers only, never shown to the author)" });
    internal.value = round.internal_notes || "";
    block.appendChild(el("div", {}, [el("label", { text: "General" }), general]));
    block.appendChild(el("div", {}, [el("label", { text: "Internal" }), internal]));
    block.appendChild(button("Save notes", function () {
      api("PUT", BASE + "/notes", { general_notes: general.value, internal_notes: internal.value }).then(reload);
    }));
    return block;
  }

  function submit(outcome) {
    var confirmText = {
      approve: "Approve and publish this dataset?",
      reject: "Reject this dataset?",
      request_changes: "Send these comments to the author?"
    }[outcome];
    if (!window.confirm(confirmText)) { return; }
    api("POST", BASE + "/submit", { outcome: outcome }).then(function (resp) {
      if (resp.status === 400) { resp.json().then(function (e) { window.alert(e.message || "Nothing to submit."); }); return; }
      if (!resp.ok) { window.alert("Submit failed."); return; }
      resp.json().then(function (data) {
        window.location = (outcome === "approve" && data.location) ? data.location : "/review/overview";
      });
    });
  }

  function renderActions() {
    return el("div", { class: "review-actions" }, [
      button("Request changes", function () { submit("request_changes"); }),
      button("Approve", function () { submit("approve"); }),
      button("Reject", function () { submit("reject"); })
    ]);
  }

  function render(root, convo) {
    root.textContent = "";
    (ctx.fields || []).forEach(function (field) { root.appendChild(renderField(convo, field)); });
    (ctx.entities || []).forEach(function (section) { root.appendChild(renderEntitySection(convo, section)); });
    var other = renderUnanchored(convo);
    if (other) { root.appendChild(other); }
    root.appendChild(renderNotes(convo));
    root.appendChild(renderActions());
  }

  function reload() {
    var root = document.getElementById("review-dataset-root");
    if (!root || !ctx.datasetUuid) { return; }
    api("GET", BASE).then(function (resp) {
      if (!resp.ok) { root.textContent = "The review conversation is unavailable."; return; }
      resp.json().then(function (convo) { render(root, convo); });
    });
  }

  document.addEventListener("DOMContentLoaded", reload);
})();
