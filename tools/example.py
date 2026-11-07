"""Non-blocking HTTP client: clone a consented voice or speak an authorized clone."""
from __future__ import annotations

import argparse
import asyncio
import base64
import os
from pathlib import Path

import httpx


class MimicClient:
    """Use one async connection pool and offload recording/output file IO."""

    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def clone(self, name: str, path: Path, transcript: str, consent: bool) -> dict:
        def read_clip():
            with path.open("rb") as stream:
                data = stream.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("Reference clip exceeds 10 MiB.")
            return base64.b64encode(data).decode("ascii")
        audio = await asyncio.to_thread(read_clip)
        reply = await self.http.post("/api/voices", json={"name": name, "audio": audio,
                                    "transcript": transcript, "consent": consent})
        reply.raise_for_status()
        return reply.json()

    async def speak(self, text: str, voice: str, output: Path) -> dict:
        reply = await self.http.post("/api/speak", json={"text": text, "voice": voice})
        reply.raise_for_status()
        result = reply.json()
        async with self.http.stream("GET", f"/api/files/{result['file_id']}") as audio:
            audio.raise_for_status()
            stream = await asyncio.to_thread(output.open, "wb")
            try:
                async for chunk in audio.aiter_bytes():
                    await asyncio.to_thread(stream.write, chunk)
            finally:
                await asyncio.to_thread(stream.close)
        return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:29404")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--text", default="Hello. This is synthetic speech.")
    parser.add_argument("--clip", type=Path)
    parser.add_argument("--transcript", default="")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("example-output.mp3"))
    args = parser.parse_args()
    token = os.environ.get("MIMIC_EXAMPLE_TOKEN", "")
    if not token:
        parser.error("Set MIMIC_EXAMPLE_TOKEN to the internal API token.")
    if args.clip and (not args.consent or not args.transcript):
        parser.error("Cloning requires --consent and --transcript.")
    async with httpx.AsyncClient(base_url=args.url, headers={"X-Internal-Token": token, "X-Requester-Username": args.owner},
                                 timeout=httpx.Timeout(7200, connect=10), follow_redirects=False) as http:
        client = MimicClient(http)
        if args.clip:
            result = await client.clone(args.voice, args.clip, args.transcript, args.consent)
            print("Cloned. Authorize this exact model_voice in the speech token projects before speaking:")
            print(result["model_voice"])
        else:
            print("Waiting for synthetic speech. CPU generation may take many minutes.")
            result = await client.speak(args.text, args.voice, args.output)
            print(result["message"])


if __name__ == "__main__":
    asyncio.run(main())
