$(document).ready(function () {
    var main_header = $('.mainhead');
    var columns_pto = $('.pto');
    var array_index_column_pto = [0]
    for (j = 0; j < columns_pto.length; j++) {
        array_index_column_pto.push(parseInt(columns_pto[j].id))
    }
    array_index_column_pto.push(parseInt(columns_pto[columns_pto.length-1].id)+1)
    for (j = 0; j < main_header.length; j++) {
        var aux_i = main_header[j].dataset.col_from
        var aux_j = main_header[j].dataset.col_to
        $('#botones')[0].innerHTML = $('#botones')[0].innerHTML + ' - <a class="toggle-vis novisto" value="' + aux_i + ',' + aux_j + '">' + main_header[j].textContent + '</a>'
    }

    var myTable = $('#mytable').DataTable({
        "sScrollX": '100%',
        rowReorder: true,
        dom: 'Bfrtip',
        buttons: [
           'excelHtml5'
        ],
        columnDefs: [
            { orderable: true, className: 'reorder', targets: array_index_column_pto },
            { orderable: false, targets: '_all' }
        ]
    });

    $('a.toggle-vis').on('click', function (e) {
        e.preventDefault();
        // Get the column API object
        var minmax = $(this).attr('value');
        var aux = minmax.split(',')
        var min = parseInt(aux[0])
        var max = parseInt(aux[1])
        for (i = min; i <= max; i++) {
            var column = myTable.column(i);
            column.visible(!column.visible());
        }
        if ($(this).hasClass('visto')){
            $(this).removeClass('visto')
            $(this).addClass('novisto')
        }
        else{
            $(this).removeClass('novisto')
            $(this).addClass('visto')
        }
    });
    

});