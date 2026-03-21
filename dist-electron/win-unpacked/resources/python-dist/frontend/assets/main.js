const cta = document.getElementById('cta');
if (cta) {
  cta.addEventListener('click', () => {
    const el = document.getElementById('contato');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  });
}
const form = document.getElementById('contatoForm');
if (form) {
  form.addEventListener('submit', e => {
    e.preventDefault();
    const nomeEl = document.getElementById('nome');
    const nome = nomeEl && 'value' in nomeEl ? nomeEl.value : '';
    alert('Obrigado, ' + nome + '. Entraremos em contato.');
    form.reset();
  });
}
