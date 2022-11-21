function render_in_form (text) { return [text].join(''); }

function or_null (value) { return (value == "" || value == "<p><br></p>") ? null : value; }

function show_message (type, message) {
    jQuery("#message")
        .addClass(type)
        .append(message)
        .fadeIn(250);
    setTimeout(function() {
        jQuery("#message").fadeOut(500, function() {
            jQuery("#message").removeClass(type).empty();
        });
    }, 5000);
}

function install_sticky_header () {
    var submenu_offset = jQuery("#submenu").offset().top;
    jQuery(window).on('resize scroll', function() {
        let scroll_offset  = jQuery(window).scrollTop();
        if (submenu_offset <= scroll_offset) {
            jQuery("#submenu").addClass("sticky");
            jQuery("#message").addClass("sticky-message");
            jQuery("h1").addClass("sticky-margin");
            jQuery("#message").width(jQuery("#content-wrapper").width());
        } else {
            jQuery("#submenu").removeClass("sticky");
            jQuery("#message").removeClass("sticky-message");
            jQuery("h1").removeClass("sticky-margin");
        }
    });
}

function install_touchable_help_icons () {
    jQuery(".help-icon").on("click", function () {
        let selector = jQuery(this).find(".help-text");
        if (selector.is(":visible") ||
            selector.css("display") != "none") {
            jQuery(this).removeClass("help-icon-clicked");
        } else {
            jQuery(this).addClass("help-icon-clicked");
        }
    });
}
