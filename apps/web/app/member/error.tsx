"use client";

export default function MemberError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main>
      <h1>Member area</h1>
      <p role="alert">The member area cannot be reached right now. Please try again in a minute.</p>
      <button className="button button-secondary" onClick={() => reset()} type="button">
        Try again
      </button>
    </main>
  );
}
