function add_dataset_to_collection (dataset_id, collection_id) {
    jQuery.ajax({
        url:         `/v2/account/collections/${collection_id}/articles`,
        type:        "POST",
        contentType: "application/json",
        accept:      "application/json",
        data:        JSON.stringify({ "articles": [dataset_id] }),
    }).done(function () {
        window.alert('Dataset succesfully added to collection');
        document.getElementById("collect").style.display="none"
    }).fail(function () {
        console.log (`Failed to add ${dataset_id}`);
        window.alert('Failed to add dataset to collection');
    });
}