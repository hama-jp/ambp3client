/**
 * AMB P3 Transponder Admin Panel
 * トランスポンダー管理画面のJavaScript
 */

// State management
let cars = [];
let currentDeleteId = null;

// DOM Elements
const addCarForm = document.getElementById('addCarForm');
const editCarForm = document.getElementById('editCarForm');
const carsTableBody = document.getElementById('carsTableBody');
const loadingMessage = document.getElementById('loadingMessage');
const errorMessage = document.getElementById('errorMessage');
const refreshBtn = document.getElementById('refreshBtn');

// Modal elements
const editModal = document.getElementById('editModal');
const deleteModal = document.getElementById('deleteModal');
const closeModal = document.getElementById('closeModal');
const closeDeleteModal = document.getElementById('closeDeleteModal');
const cancelEdit = document.getElementById('cancelEdit');
const cancelDelete = document.getElementById('cancelDelete');
const confirmDelete = document.getElementById('confirmDelete');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadCars();
    setupEventListeners();
});

// Event Listeners
function setupEventListeners() {
    // Form submissions
    addCarForm.addEventListener('submit', handleAddCar);
    editCarForm.addEventListener('submit', handleEditCar);

    // Refresh button
    refreshBtn.addEventListener('click', loadCars);

    // Modal close buttons
    closeModal.addEventListener('click', () => hideModal(editModal));
    closeDeleteModal.addEventListener('click', () => hideModal(deleteModal));
    cancelEdit.addEventListener('click', () => hideModal(editModal));
    cancelDelete.addEventListener('click', () => hideModal(deleteModal));
    confirmDelete.addEventListener('click', handleDeleteConfirm);

    // Close modals on outside click
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) hideModal(editModal);
    });
    deleteModal.addEventListener('click', (e) => {
        if (e.target === deleteModal) hideModal(deleteModal);
    });
}

// Load all cars from API
async function loadCars() {
    try {
        showLoading(true);
        hideError();

        const response = await fetch('/api/admin/cars');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        cars = await response.json();
        renderCarsTable();
        showLoading(false);
    } catch (error) {
        console.error('Error loading cars:', error);
        showError('データの読み込みに失敗しました: ' + error.message);
        showLoading(false);
    }
}

// Render cars table
function renderCarsTable() {
    if (cars.length === 0) {
        carsTableBody.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state">
                    <p>登録されているトランスポンダーがありません</p>
                    <small>上のフォームから新規登録してください</small>
                </td>
            </tr>
        `;
        return;
    }

    carsTableBody.innerHTML = cars.map(car => `
        <tr>
            <td><strong>${car.transponder_id}</strong></td>
            <td>${car.car_number !== null ? '#' + car.car_number : '-'}</td>
            <td>${car.name || '-'}</td>
            <td class="actions">
                <button class="btn btn-success btn-small" onclick="showEditModal(${car.transponder_id})">
                    ✏️ 編集
                </button>
                <button class="btn btn-danger btn-small" onclick="showDeleteModal(${car.transponder_id})">
                    🗑️ 削除
                </button>
            </td>
        </tr>
    `).join('');
}

// Add new car
async function handleAddCar(e) {
    e.preventDefault();

    const transponder_id = parseInt(document.getElementById('newTransponderId').value);
    const car_number = document.getElementById('newCarNumber').value;
    const name = document.getElementById('newName').value;

    const carData = {
        transponder_id: transponder_id,
        car_number: car_number ? parseInt(car_number) : null,
        name: name || null
    };

    try {
        const response = await fetch('/api/admin/cars', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(carData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add car');
        }

        // Success
        showSuccess('トランスポンダーを登録しました');
        addCarForm.reset();
        await loadCars();
    } catch (error) {
        console.error('Error adding car:', error);
        showError('登録に失敗しました: ' + error.message);
    }
}

// Show edit modal
function showEditModal(transponderId) {
    const car = cars.find(c => c.transponder_id === transponderId);
    if (!car) return;

    document.getElementById('editTransponderId').value = car.transponder_id;
    document.getElementById('editTransponderIdDisplay').value = car.transponder_id;
    document.getElementById('editCarNumber').value = car.car_number || '';
    document.getElementById('editName').value = car.name || '';

    showModal(editModal);
}

// Handle edit car
async function handleEditCar(e) {
    e.preventDefault();

    const transponder_id = parseInt(document.getElementById('editTransponderId').value);
    const car_number = document.getElementById('editCarNumber').value;
    const name = document.getElementById('editName').value;

    const carData = {
        car_number: car_number ? parseInt(car_number) : null,
        name: name || null
    };

    try {
        const response = await fetch(`/api/admin/cars/${transponder_id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(carData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update car');
        }

        // Success
        hideModal(editModal);
        showSuccess('トランスポンダー情報を更新しました');
        await loadCars();
    } catch (error) {
        console.error('Error updating car:', error);
        showError('更新に失敗しました: ' + error.message);
    }
}

// Show delete confirmation modal
function showDeleteModal(transponderId) {
    currentDeleteId = transponderId;
    const car = cars.find(c => c.transponder_id === transponderId);

    let displayName = `トランスポンダー ${transponderId}`;
    if (car) {
        if (car.name && car.car_number) {
            displayName = `#${car.car_number} ${car.name} (${transponderId})`;
        } else if (car.car_number) {
            displayName = `#${car.car_number} (${transponderId})`;
        } else if (car.name) {
            displayName = `${car.name} (${transponderId})`;
        }
    }

    document.getElementById('deleteMessage').textContent =
        `${displayName} を削除しますか？この操作は取り消せません。`;

    showModal(deleteModal);
}

// Handle delete confirm
async function handleDeleteConfirm() {
    if (!currentDeleteId) return;

    try {
        const response = await fetch(`/api/admin/cars/${currentDeleteId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete car');
        }

        // Success
        hideModal(deleteModal);
        showSuccess('トランスポンダーを削除しました');
        currentDeleteId = null;
        await loadCars();
    } catch (error) {
        console.error('Error deleting car:', error);
        showError('削除に失敗しました: ' + error.message);
        hideModal(deleteModal);
    }
}

// Modal helpers
function showModal(modal) {
    modal.style.display = 'flex';
}

function hideModal(modal) {
    modal.style.display = 'none';
}

// UI helpers
function showLoading(show) {
    loadingMessage.style.display = show ? 'block' : 'none';
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function hideError() {
    errorMessage.style.display = 'none';
}

function showSuccess(message) {
    // Create temporary success message
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.textContent = message;

    const container = document.querySelector('.cars-list-section');
    container.insertBefore(successDiv, container.firstChild);

    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}
