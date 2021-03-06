
$(document).ready(function() {
	$('#mainbody').delegate('#comment_form', 'submit', sendComment);
})


/* Envia el comentario con un POST, bloquea el boton hasta recibir respuesta */
function sendComment(event) {
	event.preventDefault();
	disableButtons(['#comment_button']);
	$.post($(this).attr('action'), $(this).serialize(), commentSaved);
}


/* Escribe el mensaje arriba */
function commentSaved(data) {
	if (data.error) {
		alert(data.error);
	} else if (data.ok) {
		$('#comment_field').val('');
		data['newer'] = true;
		data['comments'] = data.comment;
		if (!data.idlesson) data['idlesson'] = 0;
		commentsReceived(data);
	}
	enableButtons(['#comment_button']);
}

/* Pide mas comentarios, si newer es True pide mas recientes y si es False anteriores
	Si idlesson es menor que 0 los pide del foro y si es mayor de la clase con id idlesson*/
function askComments(idcomment, idlesson, newer) {
	disableButtons(['#ask_newer', '#ask_older']);
	path = '/more/comments/' + idcomment + '/' + idlesson + '/' + newer;
	$.getJSON(path, commentsReceived);
}

/* Coloca los mensajes recibidos en su sitio (en las paginas /forum o /lesson/id */
function commentsReceived(data) {
	if (data.idcomment == 0) {
		if (!data.newer) {
			$('#ask_older').replaceWith('<div class="btn btn-primary ' +
							'btn-sm btn-block disabled">No hay mensajes anteriores</div>')
		}
	} else {
		if (data.newer) {
			$('#comment_list > li:first').before(data.comments);
			$('#ask_newer').attr('onClick', 
						'askComments(' + data.idcomment + ',' + data.idlesson + 
						', true);return false;');
		} else {
			$('#comment_list > li:last').after(data.comments);
			$('#ask_older').attr('onClick', 
						'askComments(' + data.idcomment + ',' + data.idlesson + 
						', false);return false;');
		}
	}
	enableButtons(['#ask_newer', '#ask_older']);
}


