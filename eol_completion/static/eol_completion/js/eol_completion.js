$(document).ready(function () {
    var hd = $('.mainhead');
    var p = $('.pto');
    var aux11 = [0]
    for (j = 0; j < p.length; j++) {
        aux11.push(parseInt(p[j].id))
    }
    aux11.push(parseInt(p[p.length-1].id)+1)
    for (j = 0; j < hd.length; j++) {
        var ihd = hd[j].dataset.col_from
        var jhd = hd[j].dataset.col_to
        $('#botones')[0].innerHTML = $('#botones')[0].innerHTML + ' - <a class="toggle-vis novisto" value="' + ihd + ',' + jhd + '">' + hd[j].textContent + '</a>'
    }

    var myTable = $('#mytable').DataTable({
        "sScrollX": '100%',
        rowReorder: true,
        dom: 'Bfrtip',
        buttons: [
           'excelHtml5'
        ],
        columnDefs: [
            { orderable: true, className: 'reorder', targets: aux11 },
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