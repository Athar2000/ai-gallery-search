import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { deleteAllData } from "../api/settings";
import { useAuth } from "../context/AuthContext";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleDeleteAll() {
    setDeleting(true);
    try {
      const res = await deleteAllData();
      setResult(`Deleted ${res.deleted_photos} photos and all associated AI data.`);
      setConfirming(false);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <Link to="/" className="text-sm text-neutral-400 hover:text-neutral-200">
        ← Dashboard
      </Link>
      <h1 className="mt-1 mb-6 text-xl font-semibold tracking-tight">Settings</h1>

      <div className="mb-8 rounded-xl border border-neutral-800 p-4">
        <h2 className="mb-2 text-sm font-medium text-neutral-300">Account</h2>
        <p className="text-sm text-neutral-400">{user?.email}</p>
        <button
          onClick={() => {
            logout();
            navigate("/login", { replace: true });
          }}
          className="mt-3 rounded-lg border border-neutral-800 px-3 py-1.5 text-sm hover:border-neutral-600"
        >
          Log out
        </button>
      </div>

      <div className="rounded-xl border border-red-900/50 p-4">
        <h2 className="mb-1 text-sm font-medium text-red-400">Danger zone</h2>
        <p className="mb-3 text-xs text-neutral-500">
          Permanently deletes every photo, thumbnail, embedding, detected face/object, person, album, and search
          history for your account. Your login itself is kept. This cannot be undone.
        </p>

        {result && <p className="mb-3 text-xs text-emerald-400">{result}</p>}

        {!confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-red-900 px-3 py-1.5 text-sm text-red-400 hover:border-red-700"
          >
            Delete all photos and AI data
          </button>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-red-300">Are you sure? This cannot be undone.</p>
            <div className="flex gap-2">
              <button
                onClick={handleDeleteAll}
                disabled={deleting}
                className="rounded-lg bg-red-900 px-3 py-1.5 text-sm text-red-100 disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Yes, delete everything"}
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="rounded-lg border border-neutral-800 px-3 py-1.5 text-sm hover:border-neutral-600"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
