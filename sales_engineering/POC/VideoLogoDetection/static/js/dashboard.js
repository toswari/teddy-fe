const projectsEndpoint = '/api/projects';
const videosEndpoint = '/api/videos';

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || 'Request failed');
  }
  return response.json();
}

async function hydrateDashboard() {
  const projects = await fetchJSON(projectsEndpoint);
  if (!projects.length) {
    document.getElementById('active-project').textContent = 'No projects yet';
    return;
  }
  const active = projects[0];
  document.getElementById('active-project').textContent = active.name;
  document.getElementById('project-description').textContent = active.description;
}

hydrateDashboard().catch((err) => console.error(err));
