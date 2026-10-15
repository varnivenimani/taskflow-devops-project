document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("taskModal");
    const taskForm = document.getElementById("taskForm");
    const taskTableBody = document.getElementById("taskTableBody");

    if (!modal || !taskForm || !taskTableBody) {
        return;
    }

    const csrfToken = document.querySelector(
        'meta[name="csrf-token"]'
    ).content;

    const taskId = document.getElementById("taskId");
    const taskTitle = document.getElementById("taskTitle");
    const taskDescription = document.getElementById("taskDescription");
    const taskPriority = document.getElementById("taskPriority");
    const taskStatus = document.getElementById("taskStatus");
    const taskDueDate = document.getElementById("taskDueDate");

    const searchInput = document.getElementById("searchTasks");
    const statusFilter = document.getElementById("filterStatus");
    const priorityFilter = document.getElementById("filterPriority");

    let tasks = [];

    function openModal(task = null) {
        taskForm.reset();

        if (task) {
            document.getElementById("modalTitle").textContent = "Edit Task";

            taskId.value = task.id;
            taskTitle.value = task.title;
            taskDescription.value = task.description || "";
            taskPriority.value = task.priority;
            taskStatus.value = task.status;
            taskDueDate.value = task.due_date || "";
        } else {
            document.getElementById("modalTitle").textContent = "Add New Task";
            taskId.value = "";
        }

        modal.hidden = false;
        taskTitle.focus();
    }

    function closeModal() {
        modal.hidden = true;
        taskForm.reset();
        taskId.value = "";
    }

    [
        "addTaskTop",
        "addTaskMain",
        "addTaskSidebar"
    ].forEach(id => {
        const button = document.getElementById(id);

        if (button) {
            button.addEventListener("click", () => openModal());
        }
    });

    document.getElementById("closeTaskModal")
        .addEventListener("click", closeModal);

    document.getElementById("cancelTask")
        .addEventListener("click", closeModal);

    modal.addEventListener("click", event => {
        if (event.target === modal) {
            closeModal();
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && !modal.hidden) {
            closeModal();
        }
    });

    async function loadTasks() {
        try {
            const response = await fetch("/api/tasks");

            if (!response.ok) {
                throw new Error("Unable to load tasks");
            }

            tasks = await response.json();

            renderTasks();
            updateStats();
        } catch (error) {
            taskTableBody.innerHTML = "";

            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 5;
            cell.className = "empty-state";
            cell.textContent = "Unable to load tasks. Please refresh.";

            row.appendChild(cell);
            taskTableBody.appendChild(row);

            console.error(error);
        }
    }

    function createCell(text) {
        const cell = document.createElement("td");
        cell.textContent = text;
        return cell;
    }

    function createBadge(text, className) {
        const badge = document.createElement("span");

        badge.className = `badge ${className}`;
        badge.textContent = text;

        return badge;
    }

    function renderTasks() {
        const search = searchInput.value.toLowerCase().trim();
        const selectedStatus = statusFilter.value;
        const selectedPriority = priorityFilter.value;

        const filteredTasks = tasks.filter(task => {
            const matchesSearch =
                task.title.toLowerCase().includes(search) ||
                (task.description || "").toLowerCase().includes(search);

            const matchesStatus =
                selectedStatus === "All" ||
                task.status === selectedStatus;

            const matchesPriority =
                selectedPriority === "All" ||
                task.priority === selectedPriority;

            return matchesSearch && matchesStatus && matchesPriority;
        });

        taskTableBody.innerHTML = "";

        if (filteredTasks.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 5;
            cell.className = "empty-state";
            cell.textContent = "No tasks found. Add your first task!";

            row.appendChild(cell);
            taskTableBody.appendChild(row);

            return;
        }

        filteredTasks.forEach(task => {
            const row = document.createElement("tr");

            const titleCell = document.createElement("td");

            const title = document.createElement("div");
            title.className = "task-title";
            title.textContent = task.title;

            const description = document.createElement("div");
            description.className = "task-description";
            description.textContent = task.description || "No description";

            titleCell.appendChild(title);
            titleCell.appendChild(description);

            const priorityCell = document.createElement("td");

            priorityCell.appendChild(
                createBadge(
                    task.priority,
                    `priority-${task.priority.toLowerCase()}`
                )
            );

            const statusCell = document.createElement("td");

            statusCell.appendChild(
                createBadge(
                    task.status,
                    `status-${task.status.toLowerCase().replaceAll(" ", "-")}`
                )
            );

            const dueDateCell = createCell(task.due_date || "No due date");

            const actionsCell = document.createElement("td");
            const actions = document.createElement("div");

            actions.className = "action-buttons";

            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "btn-edit";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => openModal(task));

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "btn-delete";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener(
                "click",
                () => deleteTask(task.id)
            );

            actions.appendChild(editButton);
            actions.appendChild(deleteButton);
            actionsCell.appendChild(actions);

            row.appendChild(titleCell);
            row.appendChild(priorityCell);
            row.appendChild(statusCell);
            row.appendChild(dueDateCell);
            row.appendChild(actionsCell);

            taskTableBody.appendChild(row);
        });
    }

    function updateStats() {
        document.getElementById("totalTasks").textContent = tasks.length;

        document.getElementById("pendingTasks").textContent =
            tasks.filter(task => task.status === "Pending").length;

        document.getElementById("progressTasks").textContent =
            tasks.filter(task => task.status === "In Progress").length;

        document.getElementById("completedTasks").textContent =
            tasks.filter(task => task.status === "Completed").length;
    }

    taskForm.addEventListener("submit", async event => {
        event.preventDefault();

        const id = taskId.value;

        const taskData = {
            title: taskTitle.value.trim(),
            description: taskDescription.value.trim(),
            priority: taskPriority.value,
            status: taskStatus.value,
            due_date: taskDueDate.value
        };

        if (!taskData.title) {
            alert("Please enter a task title.");
            return;
        }

        const url = id ? `/api/tasks/${id}` : "/api/tasks";
        const method = id ? "PUT" : "POST";

        const saveButton = document.getElementById("saveTaskButton");
        saveButton.disabled = true;

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify(taskData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "Unable to save task");
            }

            closeModal();
            await loadTasks();

        } catch (error) {
            alert(error.message);
            console.error(error);
        } finally {
            saveButton.disabled = false;
        }
    });

    async function deleteTask(id) {
        if (!confirm("Are you sure you want to delete this task?")) {
            return;
        }

        try {
            const response = await fetch(`/api/tasks/${id}`, {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": csrfToken
                }
            });

            if (!response.ok) {
                throw new Error("Unable to delete task");
            }

            await loadTasks();

        } catch (error) {
            alert(error.message);
            console.error(error);
        }
    }

    searchInput.addEventListener("input", renderTasks);
    statusFilter.addEventListener("change", renderTasks);
    priorityFilter.addEventListener("change", renderTasks);

    loadTasks();
});