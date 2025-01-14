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

function _featured_institutions_count() {
    let count = 0;
    jQuery('#search-filter-content-institutions ul li').each(function() {
        if (this.classList.contains("featured")) {
            count += 1;
        }
    });
    return count;
}

function toggle_filter_institutions_showmore(flag) {
    if (flag) {
        let featured_count = _featured_institutions_count();
        jQuery('#search-filter-content-institutions ul li').css('display', 'none');
        jQuery('#search-institutions-show-more').show();

        if (featured_count > 0) {
            jQuery('#search-filter-content-institutions ul li').slice(0, featured_count).show();
        } else {
            // Show every institution if there are no featured institutions.
            jQuery('#search-filter-content-institutions ul li').show();
        }
   } else {
       jQuery('#search-filter-content-institutions ul li').show();
       jQuery('#search-institutions-show-more').hide();
   }
}

function toggle_filter_licenses_showmore(flag) {
    if (flag) {
        jQuery('#search-filter-content-licenses ul li').css('display', 'none');
        jQuery('#search-licenses-show-more').show();
        jQuery('#search-filter-content-licenses ul li').slice(0, 5).show();
   } else {
       jQuery('#search-filter-content-licenses ul li').show();
       jQuery('#search-licenses-show-more').hide();
   }
}

function toggle_checkbox_subcategories(parent_category_id, force_on=false) {
    let parent_category_checkbox = document.getElementById(`checkbox_categories_${parent_category_id}`);
    let subcategories = document.getElementById(`subcategories_of_${parent_category_id}`);
    if (subcategories === null) {
        return;
    }
    if (force_on) {
        subcategories.style.display = "block";
        return;
    }

    if (parent_category_checkbox.checked) {
        subcategories.style.display = "block";
        jQuery(`#subcategories_of_${parent_category_id} input[type='checkbox']`).each(function() {
            this.checked = false;
        });
    } else {
        jQuery(`#subcategories_of_${parent_category_id} input[type='checkbox']`).each(function() {
            this.checked = false;
        });
        subcategories.style.display = "none";
    }
}

function clear_checkbox_parentcategory(parent_category_id) {
    let parent_category_checkbox = document.getElementById(`checkbox_categories_${parent_category_id}`);
    if (parent_category_checkbox.checked) {
        parent_category_checkbox.checked = false;
    }
}

function toggle_filter_categories_showmore(flag) {
    if (flag) {
        jQuery('#search-filter-content-categories ul li').css('display', 'none');
        jQuery('#search-categories-show-more').show();
        if (enable_subcategories) {
            jQuery('#search-filter-content-categories ul li').slice(0, 75).show();
            jQuery(`#search-filter-content-categories input[type='checkbox']`).each(function() {
                if (this.id.startsWith("checkbox_categories_")) {
                    toggle_checkbox_subcategories(this.id.split("_")[2]);
                }
            });
        } else {
            jQuery('#search-filter-content-categories ul li').slice(0, 10).show();
        }
   } else {
       jQuery('#search-filter-content-categories ul li').show();
       jQuery('#search-categories-show-more').hide();
   }
}

function toggle_filter_apply_button(flag) {
    let primary_color = _corporate_background_color();
    let color = flag ? primary_color : "#eeeeee";
    let cursor = flag ? "pointer" : "default";
    let color_text = flag ? "white" : "#cccccc";
    let classes = flag ? ["enabled", "disabled"] : ["disabled", "enabled"];
    jQuery("#search-filter-apply-button").css("background", color).css("color", color_text).css("cursor", cursor);
    jQuery("#search-filter-apply-button").addClass(classes[0]).removeClass(classes[1]);
}

function toggle_filter_reset_button(flag) {
    let primary_color = _corporate_background_color();
    let color = flag ? primary_color : "#eeeeee";
    let cursor = flag ? "pointer" : "default";
    let color_text = flag ? "white" : "#cccccc";
    let classes = flag ? ["enabled", "disabled"] : ["disabled", "enabled"];
    jQuery("#search-filter-reset-button").css("background", color).css("color", color_text).css("cursor", cursor);
    jQuery("#search-filter-reset-button").addClass(classes[0]).removeClass(classes[1]);
}

function toggle_filter_input_text(id, flag) {
    if (flag) {
        jQuery(`#${id}`).show();

        // Disable all the checkboxes if the 'Other' checkbox for institutions is checked.
        if (id === "textinput_institutions_other") {
            jQuery("#search-filter-content-institutions input[type='checkbox']").each(function() {
                if (this.id === "checkbox_institutions_other") {
                    return;
                }
                this.disabled = flag;
                this.checked = !flag;
            });
        }

    } else {
        jQuery(`#${id}`).val("");
        jQuery(`#${id}`).hide();

        // Enable the other checkboxes if the 'Other' checkbox for institutions is unchecked.
        if (id === "textinput_institutions_other") {
            jQuery("#search-filter-content-institutions input[type='checkbox']").each(function() {
                this.disabled = flag;
            });
        }
    }
}

function toggle_view_mode(mode) {
    if (mode !== "list" && mode !== "tile") {
        return;
    }

    let primary_color = _corporate_background_color();

    if (mode === "tile") {
        jQuery('#search-results-list-view').hide();
        jQuery('#search-results-tile-view').show();
        jQuery('#list-view-mode').css('color', 'darkgray');
        jQuery('#tile-view-mode').css('color', primary_color);
    } else {
        jQuery('#search-results-list-view').show();
        jQuery('#search-results-tile-view').hide();
        jQuery('#list-view-mode').css('color', primary_color);
        jQuery('#tile-view-mode').css('color', 'darkgray');
    }

    let page_preferences = new PagePreferences();
    page_preferences.save("view_mode", mode);
}

function toggle_sort_by(sort_by) {
    if (!sort_by.startsWith("title_") && !sort_by.startsWith("date_")) {
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
        toggle_filter_institutions_showmore(true);
        toggle_filter_licenses_showmore(true);
    });

    // Collapse the list if 'Show more' is clicked.
    jQuery('#search-categories-show-more').click(function() {
        toggle_filter_categories_showmore(false);
    });
    jQuery('#search-institutions-show-more').click(function() {
        toggle_filter_institutions_showmore(false);
    });
    jQuery('#search-licenses-show-more').click(function() {
        toggle_filter_licenses_showmore(false);
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

                if (target_element.classList.contains("parentcategory")) {
                    let parent_category_id = target_element.id.split("_").pop();
                    toggle_checkbox_subcategories(parent_category_id);
                } else if (target_element.classList.contains("subcategory")) {
                    let parent_category_id = jQuery(target_element).parent().parent().prop("id").split("_").pop();
                    clear_checkbox_parentcategory(parent_category_id);
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

    // show more licenses if 'Show more' for licenses is clicked.
    jQuery('#search-licenses-show-more').click(function() {
        toggle_filter_licenses_showmore(false);
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

                if (target_element.classList.contains("parentcategory")) {
                    let parent_category_id = target_element.id.split("_").pop();
                    toggle_checkbox_subcategories(parent_category_id);
                } else if (target_element.classList.contains("subcategory")) {
                    let parent_category_id = jQuery(target_element).parent().parent().prop("id").split("_").pop();
                    update_checkbox_parentcategory(parent_category_id);
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
    jQuery("#textinput_publisheddate_other").keyup(function() {
        toggle_filter_apply_button(true);
        toggle_filter_reset_button(true);
    });
    jQuery("#textinput_publisheddate_other").change(function() {
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
                if (filter_name == "institutions") {
                    toggle_filter_institutions_showmore(false);
                }

                if (filter_name == "licenses") {
                    toggle_filter_licenses_showmore(false);
                }

                if (filter_name == "categories") {
                    toggle_filter_categories_showmore(false);
                }

                for (let value of values) {
                    value = value.replace(/[^a-zA-Z0-9-_]/g, '');
                    let checkbox_id = `checkbox_${filter_name}_${value}`;
                    let checkbox_id_element = jQuery(`#${checkbox_id}`);
                    if (checkbox_id_element.length > 0) {
                        jQuery(`#${checkbox_id}`).prop("checked", true);
                        if (filter_name == "categories") {
                            if (enable_subcategories) {
                                let checkbox_id_class = checkbox_id_element.prop("class");
                                if (checkbox_id_class) {
                                    let classes = checkbox_id_class.split(" ");
                                    if (classes.includes("subcategory")) {
                                        let parent_category_id = jQuery(checkbox_id_element).parent().parent().prop("id").split("_").pop();
                                        toggle_checkbox_subcategories(parent_category_id, force_on=true);
                                        jQuery(`#${checkbox_id}`).prop("checked", true);
                                    }
                                }
                            }
                        }
                    }

                    if (filter_name == "institutions") {
                        toggle_filter_institutions_showmore(false);
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
    let api_collection_url = "/v2/collections/search";
    let api_dataset_url    = "/v3/datasets/search";
    let target_api_url     = null;
    let url_params         = parse_url_params();
    let request_params     = {};

    // If the selected institutions have separate groups for students,
    // add the associated groups too.
    if ("institutions" in url_params) {
        let institutions = {};
        let hidden_institutions = {};
        let checked_institutions = {};
        jQuery(`#search-filter-content-institutions label`).each(function() {
            let institution_name = this.innerText.trim();
            let institution_id   = this.attributes["for"].value;
            let hidden = false;
            if ("hidden" in this.attributes) {
                hidden = true;
            }

            if (hidden) {
                hidden_institutions[institution_name] = institution_id;
            } else {
                institutions[institution_name] = institution_id;
            }

            institutions[institution_name] = {
                "id": institution_id,
                "hidden": hidden,
            };
        });

        for (let institution of url_params["institutions"].split(",")) {
            let institution_id = `checkbox_institutions_${institution}`;
            let institution_name = jQuery(`label[for='${institution_id}']`).text().trim();

            checked_institutions[institution_name] = institution_id;
        }

        for (let institution_name of Object.keys(hidden_institutions)) {
            let associated_institution_name = institution_name.substring(0, institution_name.length - " Students".length);
            if (associated_institution_name in checked_institutions) {
                let id = hidden_institutions[institution_name].slice("checkbox_institutions_".length);
                url_params["institutions"] += `,${id}`;
            }
        }
    }

    if ("datatypes" in url_params && url_params["datatypes"] === "collection") {
        target_api_url = api_collection_url;
    } else {
        target_api_url = api_dataset_url;
        request_params["item_type"] = url_params["datatypes"];
    }

    if ("searchscope" in url_params && typeof(url_params["searchscope"]) === "string" && url_params["searchscope"].length > 0) {
        request_params["search_scope"] = _split_comma_separated_string(url_params["searchscope"]);
    } else {
        // If searchscope is not selected, search in title, description, and tags.
        request_params["search_scope"] = ["title", "description", "tag", "author"];
    }

    if ("searchoperator" in url_params && typeof(url_params["searchoperator"]) === "string" && url_params["searchoperator"].length > 0) {
        request_params["search_operator"] = url_params["search_operator"];
    } else {
        request_params["search_operator"] = "AND";
    }

    if (("filetypes" in url_params && typeof(url_params["filetypes"]) === "string" && url_params["filetypes"].length > 0) || ("filetypes_other" in url_params && typeof(url_params["filetypes_other"]) === "string" && url_params["filetypes_other"].length > 0)) {
        request_params["search_format"] = _split_comma_separated_string(url_params["filetypes"]);
        if ("filetypes_other" in url_params && typeof(url_params["filetypes_other"]) === "string" && url_params["filetypes_other"].length > 0) {
            let filetypes_other = url_params["filetypes_other"];
            filetypes_other = trim_single_word(filetypes_other);
            request_params["search_format"].push(filetypes_other);
        }
    }

    if ("publisheddate" in url_params && typeof(url_params["publisheddate"]) === "string" && url_params["publisheddate"].length > 0) {
        let today = new Date();
        let year = today.getFullYear() - url_params["publisheddate"];
        let new_date = new Date(year, 0, 1);
        let since_date = new_date.toISOString();
        request_params["published_since"] = `${since_date}`;
    } else if ("publisheddate_other" in url_params && typeof(url_params["publisheddate_other"]) === "string" && url_params["publisheddate_other"].length > 0) {
        let new_date = new Date(url_params["publisheddate_other"]);
        let since_date = new_date.toISOString();
        request_params["published_since"] = `${since_date}`;
    }

    if (("licenses" in url_params && typeof(url_params["licenses"]) === "string" && url_params["licenses"].length > 0)) {
        request_params["licenses"] = _split_comma_separated_string(url_params["licenses"]);
    }

    if (("categories" in url_params && typeof(url_params["categories"]) === "string" && url_params["categories"].length > 0)) {
        request_params["categories"] = _split_comma_separated_string(url_params["categories"]);
    }

    if (("institutions" in url_params && typeof(url_params["institutions"]) === "string" && url_params["institutions"].length > 0)) {
        request_params["groups"] = _split_comma_separated_string(url_params["institutions"]);
    }

    if ("institutions_other" in url_params && typeof(url_params["institutions_other"]) === "string" && url_params["institutions_other"].length > 0) {
        request_params["organizations"] = trim_single_word(url_params["institutions_other"]);
    }

    request_params["search_for"] = url_params["search"];
    if (url_params["q"]) {
        request_params["search_for"] = url_params["q"];
    }

    request_params["page_size"] = page_size;
    request_params["is_latest"] = 1;
    request_params["page"] = "page" in url_params ? url_params["page"] : 1;

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
        let url_container = item.url_public_html;

        // Collections don't have .url_public_html and .url returns json.
        if (!url_container) {
            url_container = "/collections/" + uuid;
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
        html_tile_view += `<a href="${url_container}">`;
        html_tile_view += `<img class="tile-preview" src="${preview_thumb}" aria-hidden="true" alt="thumbnail for ${uuid}" />`;
        html_tile_view += `</a>`;
        html_tile_view += `<div class="tile-matches" id="article_${uuid}"></div>`;
        html_tile_view += `<div class="tile-title"><a href="${url_container}">${title}</a></div>`;

        if (revision) {
            html_tile_view += `<div class="tile-revision">Revision ${revision}</div>`;
        }
        html_tile_view += `<div class="tile-date">Posted on ${posted_date}</div>`;
        html_tile_view += `<div class="tile-authors"> </div>`;
        html_tile_view += `</div>`;

        html_list_view += '<tr>';
        html_list_view += `<td><a href="${url_container}">${title}</a></td><td style="text-align: center">${posted_date}</td>`;
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
        toggle_sort_by("date_dsc");
    }
}

function sort_search_results(sort_by) {
    let search_results_list = jQuery(".corporate-identity-table");
    // the first <tr> is the header row, so find the second <tr>
    let list_items = search_results_list.find("tr:gt(0)").get();

    try {
        list_items.sort(function(a, b) {
            // title: column 1, date: column 2
            let keyA = null;
            let keyB = null;

            if (sort_by.startsWith("date_")) {
                keyA = jQuery(a).children("td").eq(1).text();
                keyB = jQuery(b).children("td").eq(1).text();
                keyA = new Date(keyA);
                keyB = new Date(keyB);
            } else if (sort_by.startsWith("title_")) {
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

        if (sort_by.endsWith("_dsc")) {
            list_items.reverse();
        }
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

            if (sort_by.startsWith("date_")) {
                keyA = jQuery(a).children("div").eq(2).text();
                keyB = jQuery(b).children("div").eq(2).text();
                keyA = keyA.split(" ").pop();
                keyB = keyB.split(" ").pop();
                keyA = new Date(keyA);
                keyB = new Date(keyB);
            } else if (sort_by.startsWith("title_")) {
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

        if (sort_by.endsWith("_dsc")) {
            tile_items.reverse();
        }
        jQuery.each(tile_items, function(i, tile) {
            search_results_tiles.append(tile);
        });
    } catch (error) {}
}

function trim_single_word(word) {
    return word.replace(/\s+.*$/g, '');
}

function _corporate_background_color() {
    let rgb = jQuery(".corporate-identity-background").css("background");
    if (rgb === undefined) {
        return "#000000";
    }
    return `#${rgb.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\).*$/).slice(1).map(n => parseInt(n, 10).toString(16).padStart(2, '0')).join('')}`;
}

function _split_comma_separated_string(value) {
    let values = [];
    if (value && value.length > 0) {
        for (let v of value.split(",")) {
            values.push(v);
        }
    }
    return values;
}
