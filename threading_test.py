# GIL (Global Interpreter Lock)

# Threading in Python is always limited by the GIL for CPU-bound work.
# Important Clarification:
#
# I/O-bound tasks (network, file, DB) → Threading works well (GIL is released during I/O)
# CPU-bound tasks (calculations, data processing, loops) → Threading is limited by GIL

# When GIL is released:
#
# During I/O operations (await, time.sleep, network calls)
# During C extensions (numpy, pandas, etc.)

# await asyncio.sleep(1)     # I/O
# response = requests.get(url) # Network
#
# for i in range(10_000_000): # CPU heavy
#     result += i * i

# This is why we have different tools:
#
# threading → I/O bound
# asyncio → I/O bound (better)
# multiprocessing → CPU bound

# ================================================================

# Asyncio (Good for I/O bound)
# runs tasks in concurrency (not parallel)

# Key Difference:
# Concurrent = Tasks take turns (fast switching)
# Parallel = Tasks run at the same time on multiple cores

# asyncio is Python’s built-in library for writing asynchronous (concurrent) code.
# It allows your program to handle many tasks at the same time without using multiple threads
# — especially useful for I/O-bound operations (waiting for network, database, files, etc.).

# In practice for I/O:
# For network calls, file operations, etc., concurrent (asyncio) is often faster and more efficient than true parallel.

# Key Concepts:
# async def → Defines an asynchronous function
# await → "Pause here until this operation finishes, but don't block other requests"
# asyncio → The engine that manages all the concurrent operations

# Why we use asyncio in FastAPI:
# FastAPI is async-first. It uses asyncio under the hood to handle many requests efficiently.
# When using FastAPI, you usually don't need to import asyncio yourself.

# Why?
# FastAPI (built on Starlette + Uvicorn) manages the asyncio event loop for you automatically.
# You only write async def and await, and FastAPI handles the rest behind the scenes.

# When you do need to import asyncio in a FastAPI project:

# Only in these cases:
# Running background tasks
# Creating multiple concurrent tasks
# Writing custom async utilities
# Testing with pytest-asyncio

# Best for: Web APIs, network calls, file I/O

# Default choice for I/O bound: Asyncio
# Threading is good for:
# Simple fire-and-forget tasks
# When you need to integrate with blocking libraries
# GUI applications (Tkinter, PyQt)
#
# Avoid threading for heavy CPU work.

import asyncio
import time

import httpx


async def io_bound_task(name):
    print(f"Task {name} started")
    await asyncio.sleep(1)  # Simulate I/O (network, DB), sleeps for 1 second
    print(f"Task {name} completed")
    return name


async def run_async():
    start = time.time()

    tasks = [io_bound_task(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    print(f"Asyncio took: {time.time() - start:.2f} seconds")


# Practical example

import threading


# # Best for most I/O work
async def fetch_url(url):
    async with httpx.AsyncClient as client:
        response = await client.get(url)
        return response.text


def send_email_background(user_email):
    threading.Thread(target=send_email_1, args=(user_email,)).start()


def send_email_1():
    return


# ================================================================

# Multiprocessing (True Parallelism)

# Best for: CPU-heavy tasks (data processing, ML, calculations)

from multiprocessing import Pool
import time


def cpu_bound_task(n):
    count = 0
    for i in range(n):
        count += i * i
    return count


def run_with_multiprocessing():
    start = time.time()

    with Pool(processes=4) as pool:
        results = pool.map(cpu_bound_task, [10_000_000] * 4)

    print(f"Multiprocessing took: {time.time() - start:.2f} seconds")


# ====================================================

# Threading (with GIL limitation)

# Limitation: Due to GIL, this is often no faster than single thread for CPU-bound work.

import threading
import time


def cpu_bound_task(n):
    """CPU heavy task"""
    count = 0
    for i in range(n):
        count += i * i
    return count


def run_with_threads():
    threads = []
    start = time.time()

    for _ in range(4):
        t = threading.Thread(target=cpu_bound_task, args=(10_000_000,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"Threads took: {time.time() - start:.2f} seconds")


# Use Case,         Recommended Tool,       Reason
# "I/O Bound (Network, DB, File)",Asyncio,"Best performance, single thread"
# Simple background tasks,Threading,Easier for simple cases
# CPU Bound,Multiprocessing,True parallelism
# Mixed I/O + CPU,Asyncio + ProcessPool,Hybrid approach

# =========================================

# Best Practices for File Handling in Python (2026):

# Recommendation:
# Simple cases: pathlib + asyncio.to_thread
# High performance: aiofiles
# Very large files: Streaming with aiofiles

# 1. For Simple Cases → Use pathlib (Recommended)

from pathlib import Path


async def read_file(file_path: str):
    path = Path(file_path)
    content = await asyncio.to_thread(path.read_text)
    return content


# 2. For High Performance → aiofiles
import aiofiles


async def read_large_file(file_path):
    async with aiofiles.open(file_path, mode='r') as f:
        content = await f.read()
        return content


# 3. For Very Large Files → Streaming
async def process_large_file(file_path: str):
    """Stream and process large file line by line"""

    # opens file asynchronously, and closes when done
    async with aiofiles.open(file_path, mode='r') as f:
        # reads file line by line asynchronously,
        # memory efficient (doesn't load entire file into memory)
        async for line in f:
            await process_line(line)  # Process each line


# Example Use Cases:
async def process_line(line: str):
    """Process a single line of a file"""
    line = line.strip()
    if not line:
        return

    # Example 1: CSV processing
    columns = line.split(',')
    name = columns[0]
    age = int(columns[1])

    # Example 2: Log processing
    if "ERROR" in line:
        await save_error_log(line)

    # Example 3: Data transformation
    await save_to_database(name, age)


async def save_error_log(log):
    return ""


async def save_to_database(col1, col2):
    return ""


# This is very useful for:
# Large CSV files
# Log files
# JSON lines
# Any line-based data

# Why this is good for large files:
# Low memory usage (streams line by line)
# Non-blocking (other tasks can run)
# Efficient for big log files, data files, etc.


# =========================================

# practical best-practice examples of multithreading in Python:
# 1. Background Task (Most Common Use)

# Threading (I/O Bound)
def send_email_background(user_email, subject, body):
    """Example of background task using threading"""
    """Fire and forget email sending"""

    def send_email():
        # Simulate sending email
        time.sleep(2)
        print(f"Email sent to {user_email}")

        # Start in background thread
        thread = threading.Thread(target=send_email, daemon=True)   # daemon=True, thread dies when main program ends
        thread.sttart()

# Asyncio (Best for I/O Bound)

import asyncio


async def fetch_data(url: str):
    """Example of async I/O"""
    await asyncio.sleep(1)  # Simulate network call
    return f"Data from {url}"


async def main():
    # Run multiple tasks concurrently
    tasks = [
        fetch_data("https://api1.com"),
        fetch_data("https://api2.com"),
        fetch_data("https://api3.com")
    ]

    results = await asyncio.gather(*tasks)
    return results


# 2. Parallel Data Processing (with ThreadPoolExecutor)
from concurrent.futures import ThreadPoolExecutor
import requests

def fetch_url(url):
    response = requests.get(url)
    return response.text

def fetch_multiple_urls(urls):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_url, urls))
    return results

# 3. Periodic Task (Background Worker)
def run_periodic_task(interval=60):
    def worker():
        while True:
            try:
                # Do periodic work
                print("Running periodic task...")
                time.sleep(interval)
            except Exception as e:
                print(f"Error in worker: {e}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

# Real-world Example: Parallel Data Processing

from multiprocessing import Pool, cpu_count
import time
from typing import List


def process_item(item: dict) -> dict:
    """Process a single item (CPU heavy)"""
    # Simulate heavy computation
    result = 0
    for i in range(1_000_000):
        result += i * item.get("value", 1)
    item["processed"] = result
    item["status"] = "completed"
    return item


def process_batch(items: List[dict]) -> List[dict]:
    """Process batch of items using multiprocessing"""
    num_workers = min(cpu_count(), len(items))  # Don't exceed CPU cores

    with Pool(processes=num_workers) as pool:
        results = pool.map(process_item, items)

    return results


# Example usage
if __name__ == "__main__":
    data = [{"id": i, "value": i % 10} for i in range(20)]

    start = time.time()
    processed = process_batch(data)
    duration = time.time() - start

    print(f"Processed {len(processed)} items in {duration:.2f} seconds")