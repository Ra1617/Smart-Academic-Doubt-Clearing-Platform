# Smart Academic Doubt Clearing Platform

A simple, reliable system for students and instructors to post, track, and resolve academic doubts.

- Submit questions quickly. 
- Assign and manage responses by role (student, faculty, admin).
- Attach files and track resolution status.

Getting started

1. Backend: install Python dependencies and run the API.

   pip install -r backend/requirements.txt
   python backend/app/main.py

2. Frontend: install Node dependencies and start the dev server.

   cd clearmydoubt-frontend
   npm install
   npm run dev

Secrets and safe handling

Do not commit `.env` files or other secrets. They are already ignored by `.gitignore`. Rotate any keys if they were exposed earlier.

Contributing

Fork, make changes on a branch, and open a pull request. Short, focused changes are easiest to review.

License

MIT
