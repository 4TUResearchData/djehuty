const enable_subcategories = true;
const page_size = 100;
const max_parameter_length = 255;
let filter_info = {};

class PagePreferences {
    constructor() {
        this.storage = window.sessionStorage;
    }
    save(key, val) {
        this.storage.setItem(key, JSON.stringify(val));
    }
    load(key) {
        return JSON.parse(this.storage.getItem(key));
    }
    load_all() {
        let keys = Object.keys(this.storage);
        let all = {};
        for (let key of keys) {
            try {
                all[key] = JSON.parse(this.storage.getItem(key));
            } catch (error) {
                all[key] = this.storage.getItem(key);
            }
        }
        return all;
    }
    length() {
        return this.storage.length;
    }
    remove(key) {
        this.storage.removeItem(key);
    }
    clear() {
        this.storage.clear();
    }
}

function init_search_filter_info() {
    jQuery(`.search-filter-content`).each(function() {
        let filter_id = this.id;
        let filter_name = filter_id.split("-").pop();
        filter_info[filter_name] = {
            "id": filter_id,
            "name": filter_name,
            "values": [],
        }

        filter_info[filter_name]["is_multiple"] = this.classList.contains("multiple") ? true : false;
        filter_info[filter_name]["enable_other"] = this.classList.contains("other") ? true : false;
    });
}

function parse_url_params() {
    let url_params = new URLSearchParams(window.location.search);
    let params = {};
    for (let [key, value] of url_params) {
        params[key] = value;
    }
    return params;
}

function toggle_checkbox_subcategories(parent_category_id) {
    let parent_category_checkbox = document.getElementById(`checkbox_categories_${parent_category_id}`);
    let subcategories = document.getElementById(`subcategories_of_${parent_category_id}`);
    if (subcategories === null) {
        return;
    }
    if (parent_category_checkbox.checked) {
        subcategories.style.display = "block";
    } else {
        jQuery(`#subcategories_of_${parent_category_id} input[type='checkbox']`).each(function() {
            this.checked = false;
        });
        subcategories.style.display = "none";
    }
}

function toggle_filter_categories_showmore(flag) {
    if (enable_subcategories) {
        jQuery(`#search-filter-content-categories input[type='checkbox']`).each(function() {
            if (this.id.startsWith("checkbox_categories_")) {
                toggle_checkbox_subcategories(this.id.split("_")[2]);
            }
        });
    }

    if (flag) {
        jQuery('#search-filter-content-categories ul li').css('display', 'none');
        jQuery('#show-categories-more').show();
        if (enable_subcategories) {
            jQuery('#search-filter-content-categories ul li').slice(0, 75).show();
        } else {
            jQuery('#search-filter-content-categories ul li').slice(0, 10).show();
        }
   } else {
       jQuery('#search-filter-content-categories ul li').show();
       jQuery('#show-categories-more').hide();
   }
}

function toggle_filter_apply_button(flag) {
    let color = flag ? "#f49120" : "#eeeeee";
    let cursor = flag ? "pointer" : "default";
    let color_text = flag ? "white" : "#cccccc";
    let classes = flag ? ["enabled", "disabled"] : ["disabled", "enabled"];
    jQuery("#search-filter-apply-button").css("background", color).css("color", color_text).css("cursor", cursor);
    jQuery("#search-filter-apply-button").addClass(classes[0]).removeClass(classes[1]);
}

function toggle_filter_reset_button(flag) {
    let color = flag ? "#f49120" : "#eeeeee";
    let cursor = flag ? "pointer" : "default";
    let color_text = flag ? "white" : "#cccccc";
    let classes = flag ? ["enabled", "disabled"] : ["disabled", "enabled"];
    jQuery("#search-filter-reset-button").css("background", color).css("color", color_text).css("cursor", cursor);
    jQuery("#search-filter-reset-button").addClass(classes[0]).removeClass(classes[1]);
}

function toggle_filter_input_text(id, flag) {
    if (flag) {
        jQuery(`#${id}`).show();
    } else {
        jQuery(`#${id}`).val("");
        jQuery(`#${id}`).hide();
    }
}

function toggle_view_mode(mode) {
    if (mode !== "list" && mode !== "tile") {
        return;
    }

    if (mode === "tile") {
        jQuery('#search-results-list-view').hide();
        jQuery('#search-results-tile-view').show();
        jQuery('#list-view-mode').css('color', 'darkgray');
        jQuery('#tile-view-mode').css('color', '#f49120');
    } else {
        jQuery('#search-results-list-view').show();
        jQuery('#search-results-tile-view').hide();
        jQuery('#list-view-mode').css('color', '#f49120');
        jQuery('#tile-view-mode').css('color', 'darkgray');
    }

    let page_preferences = new PagePreferences();
    page_preferences.save("view_mode", mode);
}

function toggle_sort_by(sort_by) {
    if (sort_by !== "title" && sort_by !== "date") {
        return;
    }

    jQuery('#sort-by').val(sort_by);
    sort_search_results(sort_by);

    let page_preferences = new PagePreferences();
    page_preferences.save("sort_by", sort_by);
}

function register_event_handlers() {
    // reset all checkboxes if the reset button is clicked.
    jQuery("#search-filter-reset-button").click(function() {
        jQuery(`#search-box-wrapper input [type='hidden']`).remove();
        jQuery(".search-filter-content input[type='checkbox']").each(function() {
            this.checked = false;
            jQuery(`.search-filter-content input[type='text']`).each(function() {
                toggle_filter_input_text(this.id, false);
            });
            jQuery(`.search-filter-content input[type='date']`).each(function() {
                toggle_filter_input_text(this.id, false);
            });
        });
        toggle_filter_apply_button(true);
        toggle_filter_reset_button(false);
        toggle_filter_categories_showmore(true);
    });

    // show more categories if 'Show more' text is clicked.
    jQuery('#show-categories-more').click(function() {
        toggle_filter_categories_showmore(false);
    });

    // Enable the apply button if any checkbox is checked.
    // If collection is checked, disable Search Scope and File Types.
    jQuery(".search-filter-content input[type='checkbox']").change(function() {
        let is_checked = false;
        jQuery(".search-filter-content input[type='checkbox']").each(function() {
            if (this.checked) {
                toggle_filter_apply_button(true);
                toggle_filter_reset_button(true);
                is_checked = true;
                return;
            }
        });

        if (is_checked == false) {
            toggle_filter_apply_button(true);
            toggle_filter_reset_button(true);
        }

        if (this.id === "checkbox_datatypes_collection") {
            let flag = this.checked ? true : false;
            jQuery("#search-filter-content-searchscope input[type='checkbox']").each(function() {
                this.disabled = flag;
                this.checked = false;
            });
            jQuery("#search-filter-content-filetypes input[type='checkbox']").each(function() {
                this.disabled = flag;
                this.checked = false;
            });
        }
    });

    // Register events for each filter.
    for (let filter_name of Object.keys(filter_info)) {
        let event_id = "search-filter-content-" + filter_name;
        let is_multiple = filter_info[filter_name]["is_multiple"];

        jQuery(`#${event_id} input[type='checkbox']`).change(function() {
            let target_element = this;
            if (target_element.checked) {
                if (!is_multiple) {
                    jQuery(`#${event_id} input[type='checkbox']`).each(function() {
                        this.checked = false;
                        jQuery(`#${event_id} input[type='text']`).each(function() {
                            this.value = "";
                            toggle_filter_input_text(this.id, false);
                        });
                        jQuery(`#${event_id} input[type='date']`).each(function() {
                            this.value = "";
                            toggle_filter_input_text(this.id, false);
                        });

                    });
                    target_element.checked = true;
                }
            }

            if (target_element.id.split("_").pop() === "other") {
                jQuery(`#${event_id} input[type='text']`).each(function() {
                    toggle_filter_input_text(this.id, target_element.checked);
                });
                jQuery(`#${event_id} input[type='date']`).each(function() {
                    toggle_filter_input_text(this.id, target_element.checked);
                });

            }
        });
    }

    // When the apply button is clicked, update the URL.
    jQuery("#search-filter-apply-button").click(function() {
        if (jQuery("#search-filter-apply-button").hasClass("disabled")) {
            return;
        }

        jQuery(".search-filter-content input").each(function() {
            if (this.type === "checkbox" && !this.checked) { return; }
            let filter_name = this.id.split("_")[1];
            let value       = this.value;
            if (!(filter_name in filter_info)) { return; }
            if (this.type === "checkbox" && value !== "other") {
                filter_info[filter_name]["values"].push(value);
            } else if ((this.type === "text" || this.type === "date") && value.length > 0) {
                filter_info[filter_name]["other_value"] = value;
            } else {
                return;
            }
        });

        let new_url = window.location.origin + window.location.pathname + "?";
        for (let filter_name of Object.keys(filter_info)) {
            let values = filter_info[filter_name]["values"];
            if (values.length > 0) {
                new_url += `${filter_name}=${values.join(",")}&`;
            }
            if ("other_value" in filter_info[filter_name]) {
                let other_value = filter_info[filter_name]["other_value"];
                other_value = trim_single_word(other_value);
                if (other_value && other_value.length > max_parameter_length) {
                    other_value = other_value.substring(0, max_parameter_length);
                }
                new_url += `${filter_name}_other=${other_value}&`;
            }
        }

        let search_for = jQuery("#search-box").val();
        if (search_for && search_for.length > 0) {
            if (search_for.length > max_parameter_length) {
                search_for = search_for.substring(0, max_parameter_length);
                jQuery("#search-box").val(search_for);
            }
            new_url += `search=${search_for}&`;
        }

        if (new_url.endsWith("&")) {
            new_url = new_url.slice(0, -1);
        }

        window.location.href = new_url;
    });

    jQuery("#textinput_institutions_other").keyup(function() {
        toggle_filter_apply_button(true);
        toggle_filter_reset_button(true);
    });
    jQuery("#textinput_filetypes_other").keyup(function() {
        toggle_filter_apply_button(true);
        toggle_filter_reset_button(true);
    });

    jQuery('#tile-view-mode').click(function() {
        toggle_view_mode("tile");
    });

    jQuery('#list-view-mode').click(function() {
        toggle_view_mode("list");
    });

    jQuery('#sort-by').change(function() {
        let sort_by = jQuery('#sort-by').val();
        toggle_sort_by(sort_by);
    });
}

function load_search_filters_from_url() {
    let url_params = parse_url_params();
    if (Object.keys(url_params).length > 0) {
        for (let param_name of Object.keys(url_params)) {
            let values = url_params[param_name].split(",");
            let filter_name = param_name;
            let is_other = false;
            if (param_name.endsWith("_other")) {
                filter_name = param_name.split("_")[0];
                is_other = true;
            }

            if (filter_name !== "search" && filter_name !== "page") {
                if (is_other) {
                    jQuery(`#search-box-wrapper form`).append(`<input type="hidden" name="${filter_name}_other" value="${values}">`);
                } else {
                    jQuery(`#search-box-wrapper form`).append(`<input type="hidden" name="${filter_name}" value="${values}">`);
                }
            } else if (filter_name === "search") {
                let search_for = jQuery("#search-box").val();
                if (search_for && search_for.length > 0 && search_for.length > max_parameter_length) {
                    search_for = search_for.substring(0, max_parameter_length);
                    jQuery("#search-box").val(search_for);
                }
            }

            if (filter_name in filter_info) {
                for (let value of values) {
                    let checkbox_id = `checkbox_${filter_name}_${value}`;
                    let checkbox_id_element = jQuery(`#${checkbox_id}`);
                    if (checkbox_id_element.length > 0) {
                        jQuery(`#${checkbox_id}`).prop("checked", true);
                        if (filter_name == "categories") {
                            toggle_filter_categories_showmore(true);
                            if (enable_subcategories) {
                                toggle_filter_categories_showmore(false);
                            }
                        }
                    }

                    // If collection is checked, disable Search Scope and File Types.
                    if (checkbox_id === "checkbox_datatypes_collection") {
                        jQuery("#search-filter-content-searchscope input[type='checkbox']").each(function() {
                            this.disabled = true;
                            this.checked = false;
                        });
                        jQuery("#search-filter-content-filetypes input[type='checkbox']").each(function() {
                            this.disabled = true;
                            this.checked = false;
                        });
                    }
                }

                if (is_other && "enable_other" in filter_info[filter_name] && url_params[param_name] && url_params[param_name].length > 0) {
                    let other_value = url_params[param_name];
                    let input_text_id = `textinput_${filter_name}_other`;
                    let input_text_id_element = jQuery(`#${input_text_id}`);
                    if (input_text_id_element.length > 0) {
                        input_text_id_element.val(other_value);
                        toggle_filter_input_text(input_text_id, true);
                    }
                    let checkbox_id = `checkbox_${filter_name}_other`;
                    let checkbox_id_element = jQuery(`#${checkbox_id}`);
                    if (checkbox_id_element.length > 0) {
                        jQuery(`#${checkbox_id}`).prop("checked", true);
                    }
                }
            } else {
                continue;
            }
        }
    }
}

function load_search_results() {
    let api_dataset_url    = "/v2/articles/search";
    let api_collection_url = "/v2/collections/search";
    let request_params     = parse_url_params();
    let target_api_url     = null;

    if ("datatypes" in request_params && request_params["datatypes"] === "collection") {
        target_api_url = api_collection_url;
    } else {
        target_api_url = api_dataset_url;
        request_params["item_type"] = request_params["datatypes"];
    }

    let search_for = "";
    if ("searchscope" in request_params && typeof(request_params["searchscope"]) === "string" && request_params["searchscope"].length > 0) {

        // If there's no search terms, show an error message.
        if (!("search" in request_params) || typeof(request_params["search"]) === "string" && request_params["search"].length == 0) {
            let error_message = `Search Scope requires search terms(s).`;
            jQuery("#search-error").html(error_message);
            jQuery("#search-error").show();
            return;
        }

        let temp_search_for = "";
        let items = request_params["searchscope"];
        let iterated = 0;
        for (let scope of items.split(",")) {
            iterated += 1;
            temp_search_for += `:${scope}: ${request_params["search"]} OR `;
        }
        if (temp_search_for.endsWith(" OR ")) {
            temp_search_for = temp_search_for.slice(0, -4);
        }
        if (temp_search_for.length > 0) {
            if (iterated > 1) {
                search_for = `( ${temp_search_for} )`;
            } else {
                search_for = `${temp_search_for}`;
            }
        }
    } else {
        // If searchscope is not selected, search in title, description, and tags.
        if ("search" in request_params && typeof(request_params["search"]) === "string" && request_params["search"].length > 0) {
            search_for = `( :title: ${request_params["search"]} OR :description: ${request_params["search"]} OR :tag: ${request_params["search"]} )`;
        }
    }

    if (("filetypes" in request_params && typeof(request_params["filetypes"]) === "string" && request_params["filetypes"].length > 0) || ("filetypes_other" in request_params && typeof(request_params["filetypes_other"]) === "string" && request_params["filetypes_other"].length > 0)) {
        let temp_search_for = "";
        let items = request_params["filetypes"];
        let iterated = 0;
        if (items && items.length > 0) {
            for (let scope of items.split(",")) {
                iterated += 1;
                temp_search_for += `:format: ${scope} OR `;
            }
        }
        if ("filetypes_other" in request_params && typeof(request_params["filetypes_other"]) === "string" && request_params["filetypes_other"].length > 0) {
            let filetypes_other = request_params["filetypes_other"];
            filetypes_other = trim_single_word(filetypes_other);
            temp_search_for += `:format: ${filetypes_other} OR `;
        }
        if (temp_search_for.endsWith(" OR ")) {
            temp_search_for = temp_search_for.slice(0, -4);
        }
        if (temp_search_for.length > 0) {
            if (search_for) {
                if (iterated > 1) {
                    search_for += ` AND ( ${temp_search_for} )`;
                } else {
                    search_for += ` AND ${temp_search_for}`;
                }
            } else {
                search_for += `${temp_search_for}`;
            }
        }
    }

    if ("publisheddate" in request_params && typeof(request_params["publisheddate"]) === "string" && request_params["publisheddate"].length > 0) {
        let today = new Date();
        let year = today.getFullYear() - request_params["publisheddate"];
        let new_date = new Date(year, 0, 1);
        let since_date = new_date.toISOString();
        request_params["published_since"] = `${since_date}`;
    } else if ("publisheddate_other" in request_params && typeof(request_params["publisheddate_other"]) === "string" && request_params["publisheddate_other"].length > 0) {
        let new_date = new Date(request_params["publisheddate_other"]);
        let since_date = new_date.toISOString();
        request_params["published_since"] = `${since_date}`;
    }

    if ("institutions_other" in request_params && typeof(request_params["institutions_other"]) === "string" && request_params["institutions_other"].length > 0) {
        let institutions_other = request_params["institutions_other"];
        institutions_other = trim_single_word(institutions_other);
        if (search_for) {
            search_for += ` AND :organizations: ${institutions_other}`;
        } else {
            search_for += `:organizations: ${institutions_other}`;
        }
    }

    if (search_for.length > 0) {
        request_params["search_for"] = search_for;
    } else {
        if ("search" in request_params && typeof(request_params["search"]) === "string" && request_params["search"].length > 0) {
            request_params["search_for"] = request_params["search"];
        }
    }

    request_params["group"] = request_params["institutions"];
    request_params["page_size"] = page_size;
    request_params["is_latest"] = 1;
    if (!("page" in request_params)) {
        request_params["page"] = 1;
    }

    jQuery("#search-loader").show();
    jQuery("#search-error").hide();

    jQuery.ajax({
        url:         target_api_url,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify(request_params),
        dataType:    "json"
    }).done(function (data) {
        try {
            if (data.length == 0) {
                let error_message = `No search results...`;
                jQuery("#search-error").html(error_message);
                jQuery("#search-error").show();
                return;
            }

            render_search_results(data, request_params["page"]);
        } catch (error) {
            let error_message = `Failed to get search results` +
                                `<br>reason: ${error}`;
            jQuery("#search-error").html(error_message);
            jQuery("#search-error").show();
        }
    }).fail(function (jqXHR, status, error) {
        let error_message = `Failed to get search results` +
                            `<br><br>status: ${status}` +
                            `<br>reason: ${error}`;
        jQuery("#search-error").html(error_message);
        jQuery("#search-error").show();
    }).always(function () {
        jQuery("#search-loader").hide();
    });
}

function render_search_results(data, page_number) {
    let html_tile_view = "";
    let html_list_view = "";
    html_list_view += '<table class="corporate-identity-table">';
    html_list_view += '<thead><tr><th>Dataset</th><th>Posted On</th></tr></thead>';

    for (let item of data) {
        // continue if it doesn't have a timeline.
        // Usually, embargoed datasets don't have timeline.
        if (!("timeline" in item)) {
            continue;
        }

        let uuid = item.uuid;
        let title = item.title;
        let url_dataset = item.url_public_html;

        // Collections don't have .url_public_html and .url returns json.
        if (!url_dataset) {
            url_dataset = "/collections/" + uuid;
        }

        let preview_thumb = "/static/images/dataset-thumb.svg";
        if ("thumb" in item && typeof(item.thumb) === "string" && item.thumb.length > 0 && !(item.thumb.startsWith("https://ndownloader"))) {
            preview_thumb = item.thumb;
        }

        let posted_date = item.timeline.posted;
        if (posted_date.includes("T")) {
            posted_date = posted_date.split("T")[0];
        }

        let revision = null;
        if ("revision" in item.timeline && item.timeline.revision !== null) {
            revision = item.timeline.revision;
        }

        html_tile_view += `<div class="tile-item">`;
        html_tile_view += `<a href="${url_dataset}">`;
        html_tile_view += `<img class="tile-preview" src="${preview_thumb}" aria-hidden="true" alt="thumbnail for ${uuid}" />`;
        html_tile_view += `</a>`;
        html_tile_view += `<div class="tile-matches" id="article_${uuid}"></div>`;
        html_tile_view += `<div class="tile-title"><a href="/datasets/${uuid}">${title}</a></div>`;

        if (revision) {
            html_tile_view += `<div class="tile-revision">Revision ${revision}</div>`;
        }
        html_tile_view += `<div class="tile-date">Posted on ${posted_date}</div>`;
        html_tile_view += `<div class="tile-authors"> </div>`;
        html_tile_view += `</div>`;

        html_list_view += '<tr>';
        html_list_view += `<td><a href="${url_dataset}">${title}</a></td><td style="text-align: center">${posted_date}</td>`;
        html_list_view += '</tr>';
    }

    html_list_view += `</tbody></table>`;
    html_pager = get_pager_html(data, page_number);
    jQuery("#search-results-tile-view").html(html_tile_view);
    jQuery("#search-results-list-view").html(html_list_view);
    jQuery(".search-results-pager").html(html_pager);

    update_search_results_count(data, page_number);
    // Sort the search results by the selected sort_by.
    load_search_preferences();
}

function update_search_results_count(data, current_page=1) {
    let html = "";
    if (data.length < page_size) {
        if (current_page === 1) {
            if (data.length === 1) {
                html = "<b>1</b> result found.";
            } else {
                html = `<b>${data.length}</b> results found.`;
            }
        } else {
            html = `Over <b>${page_size}</b> results found.`;
        }
    } else {
        html = `Over <b>${page_size}</b> results found.`;
    }

    jQuery("#search-results-count").html(html);
}

function get_pager_html(data, current_page=1) {
    let prev_page = Number(current_page) - 1;
    let next_page = Number(current_page) + 1;
    let html = "";

    if (data.length < page_size) {
        if (current_page === 1) {
            prev_page = null;
            next_page = null;
        } else {
            next_page = null;
        }
    } else {
        if (current_page === 1) {
            prev_page = null;
        }
    }

    let new_url_link = new URL(window.location.href);
    new_url_link.searchParams.delete('page');
    html += "";
    if (prev_page) {
        new_url_link.searchParams.append('page', prev_page);
        html += `<div><a href="${new_url_link.href}" class="pager-prev">Previous</a></div>`;
    } else {
        html += `<div style="color: lightgrey">Prev</div>`;
    }

    html += `<div class="pager-cur">Page ${current_page}</div>`;

    if (next_page) {
        new_url_link.searchParams.append('page', next_page);
        html += `<div><a href="${new_url_link.href}" class="pager-next">Next</a></div>`;
    } else {
        html += `<div style="color: lightgrey">Next</div>`;
    }
    return html;
}

function load_search_preferences() {
    let page_preferences = new PagePreferences();
    let all_preferences = page_preferences.load_all();
    if ("view_mode" in all_preferences) {
        toggle_view_mode(all_preferences["view_mode"]);
    } else {
        toggle_view_mode("tile");
    }

    if ("sort_by" in all_preferences) {
        toggle_sort_by(all_preferences["sort_by"]);
    } else {
        toggle_sort_by("date");
    }
}

function sort_search_results(sort_by) {
    //
    // Sort the list view
    //
    let search_results_list = jQuery(".corporate-identity-table");
    // the first <tr> is the header row, so find the second <tr>
    let list_items = search_results_list.find("tr:gt(0)").get();

    try {
        list_items.sort(function(a, b) {
            // title: column 1, date: column 2
            let keyA = null;
            let keyB = null;

            if (sort_by === "date") {
                keyA = jQuery(a).children("td").eq(1).text();
                keyB = jQuery(b).children("td").eq(1).text();
                keyA = new Date(keyA);
                keyB = new Date(keyB);
            } else if (sort_by === "title") {
                keyA = jQuery(a).children("td").eq(0).text();
                keyB = jQuery(b).children("td").eq(0).text();
                // Sometimes, the title has leading/trailing spaces.
                keyA = keyA.trim().toLowerCase();
                keyB = keyB.trim().toLowerCase();
            }
            if (keyA < keyB) return -1;
            if (keyA > keyB) return 1;
            return 0;
        });

        jQuery.each(list_items, function(i, row) {
            search_results_list.append(row);
        });
    } catch (error) {}

    //
    // Sort the tile view
    //
    let search_results_tiles = jQuery("#search-results-tile-view");
    let tile_items = search_results_tiles.find(".tile-item").get();

    try {
        tile_items.sort(function(a, b) {
            let keyA = null;
            let keyB = null;

            if (sort_by === "date") {
                keyA = jQuery(a).children("div").eq(2).text();
                keyB = jQuery(b).children("div").eq(2).text();
                keyA = keyA.split(" ").pop();
                keyB = keyB.split(" ").pop();
                keyA = new Date(keyA);
                keyB = new Date(keyB);
            } else if (sort_by === "title") {
                keyA = jQuery(a).children("div").eq(1).text();
                keyB = jQuery(b).children("div").eq(1).text();
                // Sometimes, the title has leading/trailing spaces.
                keyA = keyA.trim().toLowerCase();
                keyB = keyB.trim().toLowerCase();
            }
            if (keyA < keyB) return -1;
            if (keyA > keyB) return 1;
            return 0;
        });

        jQuery.each(tile_items, function(i, tile) {
            search_results_tiles.append(tile);
        });
    } catch (error) {}
}

function trim_single_word(word) {
    return word.replace(/\s+.*$/g, '');
}
