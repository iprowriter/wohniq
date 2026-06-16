// Placeholder home page. The real search experience (search box → result cards
// with explanation + risk badge) is built in milestone M5 (task T5.1).

export default function Home() {
  return (
    <main style={{ maxWidth: 640, margin: "4rem auto", fontFamily: "system-ui" }}>
      <h1>WohnIQ</h1>
      <p>AI-assisted apartment search for Berlin.</p>
      <p style={{ color: "#888" }}>Frontend scaffold — search UI coming in M5.</p>
    </main>
  );
}
