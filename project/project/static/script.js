function showUpdateOptions() {
    document.getElementById('update-options').classList.remove('hidden');
    const buttons = document.getElementsByClassName('toggle-buttons');
    for (let i = 0; i < buttons.length; i++) {
        buttons[i].style.display = 'none';
    }
}

function showForm(formId) {
    document.getElementById('update-options').classList.add('hidden');
    document.getElementById(formId).classList.remove('hidden');
}

function resetPage() {
    document.getElementById('update-options').classList.add('hidden');
    document.getElementById('update-paypal').classList.add('hidden');
    document.getElementById('update-username').classList.add('hidden');
    document.getElementById('update-password').classList.add('hidden');
    const buttons = document.getElementsByClassName('toggle-buttons');
    for (let i = 0; i < buttons.length; i++) {
        buttons[i].style.display = 'block';
    }
}
