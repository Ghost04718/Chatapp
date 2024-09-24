'use client';

import React, { useState, useEffect } from 'react';
import io, { Socket } from 'socket.io-client';

interface Room {
  id: string;
  name: string;
}

interface Message {
  user: string;
  message: string;
}

let socket: Socket;

export default function Home() {
  const [rooms, setRooms] = useState<Room[]>([{ id: 'public', name: 'Public Chat' }]);
  const [currentRoom, setCurrentRoom] = useState('public');
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [newRoomName, setNewRoomName] = useState('');
  const [newPrivateUserId, setNewPrivateUserId] = useState('');
  const [showCreateRoom, setShowCreateRoom] = useState(false);

  useEffect(() => {
    socket = io('http://localhost:3001');

    socket.on('room created', (room: Room) => {
      setRooms((prevRooms) => [...prevRooms, room]);
    });

    socket.on('chat message', (msg: Message) => {
      setMessages((prevMessages) => [...prevMessages, msg]);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const sendMessage = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (message) {
      socket.emit('chat message', message, currentRoom);
      setMessage('');
    }
  };

  const createPrivateRoom = (otherUserId: string) => {
    socket.emit('create private room', otherUserId);
  };

  const createGroupRoom = (roomName: string, participants: string[]) => {
    socket.emit('create group room', roomName, participants);
  };

  const joinRoom = (roomId: string) => {
    socket.emit('leave room', currentRoom);
    socket.emit('join room', roomId);
    setCurrentRoom(roomId);
  };

  const handleCreateRoom = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (newRoomName && newRoomName.trim() !== '') {
      createGroupRoom(newRoomName.trim(), [socket.id]);
      setNewRoomName('');
      setShowCreateRoom(false);
    }
  };

  const handleCreatePrivateRoom = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (newPrivateUserId) {
      createPrivateRoom(newPrivateUserId);
      setNewPrivateUserId('');
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-8">Real-time Chat App</h1>
        
        <div className="flex mb-4 flex-wrap">
          {rooms.map((room) => (
            <button
              key={room.id}
              onClick={() => joinRoom(room.id)}
              className={`mr-2 mb-2 px-4 py-2 rounded ${currentRoom === room.id ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
            >
              {room.name}
            </button>
          ))}
          <button
            onClick={() => setShowCreateRoom(!showCreateRoom)}
            className="mr-2 mb-2 px-4 py-2 rounded bg-green-500 text-white"
          >
            {showCreateRoom ? 'Cancel' : 'Create Room'}
          </button>
        </div>

        {showCreateRoom && (
          <div className="mb-4">
            <form onSubmit={handleCreateRoom} className="flex mb-2">
              <input
                type="text"
                value={newRoomName}
                onChange={(e) => setNewRoomName(e.target.value)}
                className="flex-grow border rounded-l px-4 py-2"
                placeholder="New room name"
              />
              <button type="submit" className="bg-green-500 text-white px-4 py-2 rounded-r">Create Group</button>
            </form>
            <form onSubmit={handleCreatePrivateRoom} className="flex">
              <input
                type="text"
                value={newPrivateUserId}
                onChange={(e) => setNewPrivateUserId(e.target.value)}
                className="flex-grow border rounded-l px-4 py-2"
                placeholder="User ID for private chat"
              />
              <button type="submit" className="bg-purple-500 text-white px-4 py-2 rounded-r">Create Private</button>
            </form>
          </div>
        )}

        <div className="border p-4 rounded-lg mb-4 max-h-96 overflow-y-auto">
          <h2 className="text-xl font-semibold mb-2">Messages in {rooms.find(r => r.id === currentRoom)?.name}</h2>
          <ul>
            {messages.map((msg, index) => (
              <li key={index} className="mb-1">
                <span className="font-bold">{msg.user}:</span> {msg.message}
              </li>
            ))}
          </ul>
        </div>

        <form onSubmit={sendMessage} className="flex">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="flex-grow border rounded-l px-4 py-2"
            placeholder="Type a message..."
          />
          <button type="submit" className="bg-blue-500 text-white px-4 py-2 rounded-r">Send</button>
        </form>
      </div>
    </main>
  );
}