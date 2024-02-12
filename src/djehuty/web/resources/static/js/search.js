function extra_render_search_page(articles, display_terms) {
  let articles_fields = {};

  // In fact, articles don't have tag field.
  let fields_mapping = {
    "title":          {"short_name": "title",    "long_name": "Keyword(s) found in Title"},
    "resource_title": {"short_name": "resource", "long_name": "Keyword(s) found in Resource Title"},
    "description":    {"short_name": "desc",     "long_name": "Keyword(s) found in Description"},
    "citation":       {"short_name": "cite",     "long_name": "Keyword(s) found in Citation"},
    "format":         {"short_name": "format",   "long_name": "Keyword(s) found in Format"},
    "tag":            {"short_name": "tag",      "long_name": "Keyword(s) found in Keyword"}
  }

  let enable_fields_palette = false;
  let fields_pallet = {
    "title":          "#FF70A6",
    "resource_title": "#F570FF",
    "description":    "#FF9770",
    "citation":       "#FFB700",
    "format":         "#ABC900",
    "tag":            "#9EBA00"
  };

  articles.forEach(function (article, article_index) {
    let match_fields = [];
    display_terms.forEach(function (display_term) {
      // if display_term's type is not string, then skip.
      if (typeof display_term !== "string") {
        return;
      }

      // if display_term has '^:.+: ' in regular expression, then remove it.
      display_term = display_term.replace(/^:.+: /, "");
      for (let field_name in fields_mapping) {
        if (field_name in article && article[field_name].toLowerCase().includes(display_term.toLowerCase())) {
          match_fields.push(field_name);
        }
      }
    });
    let div_match = document.getElementById(`article_${(article_index + 1)}`);
    let match_fields_uniq = match_fields.filter((value, index) => match_fields.indexOf(value) === index);
    if (match_fields_uniq.length > 0) {
      articles_fields[article_index] = match_fields_uniq;
    } else {
      articles_fields[article_index] = ["tag"];
    }

    if (article_index in articles_fields) {
      articles_fields[article_index].forEach(function (match_field) {
        if (enable_fields_palette) {
          jQuery(`<span class="match-badge" style="background-color: ${fields_pallet[match_field]}" title="${fields_mapping[match_field]["long_name"]}">${fields_mapping[match_field]["short_name"]}</span>`).appendTo(div_match);
        } else {
          jQuery(`<span class="match-badge" title="${fields_mapping[match_field]["long_name"]}">${fields_mapping[match_field]["short_name"]}</span>`).appendTo(div_match);
        }
      });
    }
  });

  jQuery('#list_view_mode').click(function() {
    jQuery('.tile-item').hide();
    jQuery('.list-item').show();
    jQuery('#tile_view_mode').css('color', 'darkgray');
    jQuery('#list_view_mode').css('color', '#f49120');

    if (jQuery('.list-item').html().length === 0) {
      jQuery("#search-result-wrapper").addClass("loader");
      jQuery("#search-result tbody tr").css('opacity', '0.15');

      let table_html = '';
      table_html += '<table id="search-result" class="corporate-identity-table">';
      table_html += '<thead><tr><th>Dataset</th><th style="padding-right:20px;">Posted On</th></tr></thead>';
      table_html += '<tbody>';
      articles.forEach(function (article, article_index) {
        let posted_on = article.timeline_posted;
        let title = article.title;
        if (posted_on.includes("T")) {
          posted_on = posted_on.split("T")[0];
        }
        let badge_html = '';
        let badge_string_length = 0;
        if (article_index in articles_fields) {
          articles_fields[article_index].forEach(function (match_field) {
            if (enable_fields_palette) {
              badge_html += `<span class="match-badge" style="background-color: ${fields_pallet[match_field]}" title="${fields_mapping[match_field]["long_name"]}">${fields_mapping[match_field]["short_name"]}</span>`;
            } else {
              badge_html += `<span class="match-badge" title="${fields_mapping[match_field]["long_name"]}">${fields_mapping[match_field]["short_name"]}</span>`;
            }
            badge_string_length += fields_mapping[match_field]["short_name"].length;
          });
        }
        if (badge_string_length) {
          badge_string_length += 10;
        }
        max_title_length = 150 - badge_string_length;
        if (title.length > max_title_length) {
          title = title.substring(0, max_title_length) + '...';
        }
        table_html += '<tr>';
        table_html += `<td><div style="float: left;"><a href="/datasets/${article.container_uuid}">${title}</a></div><div style="float: right;">${badge_html}</div></td><td style="padding-right:20px;">${posted_on}</td>`;
        table_html += '</tr>';
      });
      table_html += '</tbody></table>';

      jQuery('.list-item').html(table_html);

      jQuery("#search-result").DataTable({
        "order": [[ 1, 'desc' ]],
        "bInfo" : false,
        "paging": false,
        "searching": false,
        "lengthChange": false,
      });

      jQuery("#search-result").show();

    };
  });

  jQuery('#tile_view_mode').click(function() {
    jQuery('.list-item').hide();
    jQuery('.tile-item').show();
    jQuery('#list_view_mode').css('color', 'darkgray');
    jQuery('#tile_view_mode').css('color', '#f49120');
  });
};
