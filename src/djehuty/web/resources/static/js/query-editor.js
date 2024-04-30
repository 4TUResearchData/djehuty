var editor = null;

function execute_query (editor) {
    jQuery("#button-wrapper").after(
        "<div class=\"query-data-loader\">" +
            "<div class=\"title\">Loading data ...</div>" +
            "<div class=\"content\">Please wait for the results to appear.</div>" +
        "</div>");

    /* Remove the previous query results. */
    jQuery(".query-error").remove();
    jQuery("#query-results").remove();
    jQuery("#query-output").remove();
    jQuery("#query-output_wrapper").remove();

    jQuery.ajax("/admin/sparql", {
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/sparql-update"
        },
        method: "POST",
        data: editor.getValue(),
        success: function (data) {
            jQuery(".query-data-loader").remove();
            jQuery("#button-wrapper").after(
                "<h3 id=\"query-results\">Query results</h3>");

            if (data.length == 0) {
                jQuery("#query-results").after(
                    "<p id=\"query-output\">The query returned 0 rows.</p>");
            }
            else {
                jQuery("#query-results").after(`<pre id="query-output">${JSON.stringify(data)}</pre>`);
                jQuery("#query-output").addClass("display");
            }
        },
        error: function (request, status, error) {
            var errorMessage = "";
            try {
                data = JSON.parse(request.responseText);
                errorMessage = data.error.message;
            }
            catch (err) { errorMessage = error; }

            if (errorMessage == "") {
                errorMessage = "An unknown error occurred.";
            }

            jQuery(".query-data-loader").remove();
            jQuery("#button-wrapper").after(
                "<h3 id=\"query-results\">Query results</h3>" +
                "<div class=\"query-error\">" +
                    "<div class=\"title\">Error</div>" +
                    "<div class=\"content\"><pre>" + errorMessage +
                    "</pre></div></div>");
        }
    });
}

jQuery(document).ready(function() {
    let editor = ace.edit("editor");
    let session = editor.getSession();
    editor.setTheme("ace/theme/crimson_editor");
    editor.setShowPrintMargin(false);
    editor.setAutoScrollEditorIntoView(true);
    editor.setOptions({ maxLines: 120,
                        minLines: 2,
                        enableBasicAutocompletion: true,
                        enableLiveAutocompletion: true });
    session.setMode("ace/mode/sparql");
    session.setTabSize(2);

    /* Add keybindings for copying the text and for running the query. */
    editor.commands.addCommand({
        name: "copyCommand",
        bindKey: {win: "Ctrl-C",  mac: "Command-C"},
        exec: function(editor) {
            jQuery("#content").after("<textarea id=\"copyText\"></textarea>");
            let temp = document.getElementById("copyText");
            temp.value = editor.getSelectedText();
            temp.select();
            document.execCommand("copy");
            temp.remove();
            jQuery(".ace_text-input").focus();
        }, readOnly: true
    });

    editor.commands.addCommand({
        name: "executeQueryCommand",
        bindKey: {win: 'Ctrl-Enter',  mac: 'Command-Enter'},
        exec: execute_query, readOnly: true
    });

    jQuery("#execute-query-button").on("click", function (event) {
        execute_query (editor);
    });
});
