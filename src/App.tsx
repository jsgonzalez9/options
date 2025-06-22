import React from 'react';
import { Dashboard } from './components/Dashboard';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6">
          <Dashboard />
        </main>
      </div>
    </div>
  );
}

export default App;