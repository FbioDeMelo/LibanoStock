function toggleNotificacoes() {
  const container = document.getElementById('notificacoes-container');
  container.style.display = container.style.display === 'block' ? 'none' : 'block';
}

// Buscar notificações
function atualizarNotificacoes() {
  fetch(window.DJANGO.notificacoesUrl)
    .then(res => res.json())
    .then(data => {
      const container = document.getElementById('notificacoes-container');
      const dropdown = document.getElementById('notificacoes-dropdown');

      container.innerHTML = '';

      if (data.notificacoes.length === 0) {
        container.innerHTML = '<p style="padding:10px;">Nenhuma notificação</p>';
        dropdown.classList.remove('has-notifications');
      } else {
        dropdown.classList.add('has-notifications');
        data.notificacoes.forEach(n => {
          const div = document.createElement('div');
          div.classList.add('notif-item');
          div.style.padding = '10px';
          div.style.borderBottom = '1px solid #eee';
          div.style.display = 'flex';
          div.style.justifyContent = 'space-between';
          div.style.alignItems = 'center';
          div.innerHTML = `
            <span>${n.mensagem}</span>
            <button style="background:#ea005f;color:white;border:none;padding:4px 8px;border-radius:3px;cursor:pointer;" onclick="marcarVista(${n.id})">✔</button>
          `;
          container.appendChild(div);
        });
      }
    });
}

// Marcar notificação como vista
function marcarVista(id) {
  fetch(window.DJANGO.marcarVistaUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': window.DJANGO.csrfToken
    },
    body: 'id=' + id
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      atualizarNotificacoes();
    } else {
      alert(data.error);
    }
  });
}

// Atualizar a cada 30 segundos
setInterval(atualizarNotificacoes, 30000);
window.onload = atualizarNotificacoes;

// Sidebar responsiva
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('mobile-open');
}

document.addEventListener('click', function (event) {
  const sidebar = document.getElementById('sidebar');
  const menuToggle = document.querySelector('.menu-toggle');

  if (
    window.innerWidth <= 768 &&
    !sidebar.contains(event.target) &&
    !menuToggle.contains(event.target)
  ) {
    sidebar.classList.remove('mobile-open');
  }
});

let resizeTimeout;
window.addEventListener('resize', function () {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(function () {
    const sidebar = document.getElementById('sidebar');
    if (window.innerWidth > 768) {
      sidebar.classList.remove('mobile-open');
    }
  }, 250);
});

// Modal de avatar
function openAvatarModal() {
  document.getElementById('avatarModal').style.display = 'block';
}

function closeAvatarModal() {
  document.getElementById('avatarModal').style.display = 'none';
}

function setAvatar(src) {
  document.getElementById('user-avatar').src = src;
  closeAvatarModal();

  fetch(window.DJANGO.atualizarAvatarUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': window.DJANGO.csrfToken
    },
    body: 'avatar=' + encodeURIComponent(src)
  })
  .then(res => res.json())
  .then(data => {
    if (!data.success) {
      alert('Erro ao salvar avatar: ' + data.error);
    }
  });
}
