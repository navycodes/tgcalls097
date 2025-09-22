import { RTCConnection } from './rtc-connection';
import { Binding } from './binding';
import * as process from "process";
import { isMainThread } from "worker_threads";
import { getErrorMessage, LogLevel } from "./utils";

if (isMainThread) {
    const binding = new Binding();
    const connections = new Map<number, RTCConnection>();

    const logInfo = (msg: string) => {
        if (process.platform === 'win32') {
            console.log(msg);
        } else {
            console.log('\x1b[32m', msg, '\x1b[0m');
        }
    };

    const sendNotInCall = async (chatId: number, solverId: string) => {
        await binding.sendUpdate({
            action: 'update_request',
            result: 'NOT_IN_GROUP_CALL',
            chat_id: chatId,
            solver_id: solverId,
        });
    };

    binding.on('connect', async (userId: number) => {
        logInfo(`[${userId}] Started Node.js core!`);
    });

    binding.on('request', async (data: any, update_id: string) => {
        Binding.log('REQUEST: ' + JSON.stringify(data), LogLevel.INFO);
        let connection = connections.get(data.chat_id);

        try {
            switch (data.action) {
                case 'join_call':
                    if (!connection) {
                        connection = new RTCConnection(
                            data.chat_id,
                            binding,
                            data.buffer_length,
                            data.invite_hash,
                            data.stream_audio,
                            data.stream_video,
                            data.lip_sync,
                        );
                        connections.set(data.chat_id, connection);

                        try {
                            await connection.joinCall();
                            await binding.sendUpdate({
                                action: 'update_request',
                                result: 'JOINED_VOICE_CHAT',
                                chat_id: data.chat_id,
                                solver_id: data.solver_id,
                            });
                        } catch (err: any) {
                            connections.delete(data.chat_id);
                            await binding.sendUpdate({
                                action: 'update_request',
                                result: getErrorMessage(err.message),
                                chat_id: data.chat_id,
                                solver_id: data.solver_id,
                            });
                        }
                    } else {
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'ALREADY_JOINED',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    }
                    break;

                case 'leave_call':
                    if (!connection) {
                        await sendNotInCall(data.chat_id, data.solver_id);
                        break;
                    }
                    if (data.type === 'kicked_from_group') {
                        connection.stop();
                        connections.delete(data.chat_id);
                        break;
                    }
                    const result = await connection.leave_call();
                    connections.delete(data.chat_id);
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'LEFT_VOICE_CHAT',
                        error: result?.result !== 'OK' ? result?.result : undefined,
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                    break;

                case 'pause':
                case 'resume':
                    if (!connection) {
                        await sendNotInCall(data.chat_id, data.solver_id);
                        break;
                    }
                    try {
                        if (data.action === 'pause') {
                            await connection.pause();
                            await binding.sendUpdate({
                                action: 'update_request',
                                result: 'PAUSED_STREAM',
                                chat_id: data.chat_id,
                                solver_id: data.solver_id,
                            });
                        } else {
                            await connection.resume();
                            await binding.sendUpdate({
                                action: 'update_request',
                                result: 'RESUMED_STREAM',
                                chat_id: data.chat_id,
                                solver_id: data.solver_id,
                            });
                        }
                    } catch (err) {
                        Binding.log(`Error on ${data.action}: ${err}`, LogLevel.ERROR);
                    }
                    break;

                case 'change_stream':
                    if (!connection) {
                        await sendNotInCall(data.chat_id, data.solver_id);
                        break;
                    }
                    try {
                        await connection.changeStream(
                            data.stream_audio,
                            data.stream_video,
                            data.lip_sync,
                        );
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'CHANGED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } catch (err) {
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'STREAM_DELETED',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    }
                    break;

                case 'mute_stream':
                case 'unmute_stream':
                    if (!connection) {
                        await sendNotInCall(data.chat_id, data.solver_id);
                        break;
                    }
                    if (data.action === 'mute_stream') {
                        connection.mute();
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'MUTED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } else {
                        connection.unmute();
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'UNMUTED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    }
                    break;

                case 'played_time':
                    if (connection) {
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'PLAYED_TIME',
                            time: connection.getTime(),
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } else {
                        await sendNotInCall(data.chat_id, data.solver_id);
                    }
                    break;
            }
        } catch (err) {
            Binding.log(`Unhandled error on ${data.action}: ${getErrorMessage((err as any).message)}`, LogLevel.ERROR);
        } finally {
            binding.resolveUpdate(data.chat_id, update_id);
        }
    });
}



/* import {RTCConnection} from './rtc-connection';
import { Binding } from './binding';
import * as process from "process";
import {isMainThread} from "worker_threads";
import {getErrorMessage, LogLevel} from "./utils";

if (isMainThread) {
    const binding = new Binding();
    const connections = new Map<number, any>();
    binding.on('connect', async (userId: number) => {
        let text = `[${userId}] Started Node.js core!`;
        if (process.platform === 'win32') {
            console.log(text);
        } else {
            console.log('\x1b[32m', text, '\x1b[0m');
        }
    });
    binding.on('request', async function (data: any, update_id: string) {
        Binding.log('REQUEST: ' + JSON.stringify(data), LogLevel.INFO);
        let connection: RTCConnection = connections.get(data.chat_id);
        switch (data.action) {
            case 'join_call':
                if (!connection) {
                    connection = new RTCConnection(
                        data.chat_id,
                        binding,
                        data.buffer_length,
                        data.invite_hash,
                        data.stream_audio,
                        data.stream_video,
                        data.lip_sync,
                    );
                    connections.set(data.chat_id, connection);
                    try {
                        await connection.joinCall()
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'JOINED_VOICE_CHAT',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } catch (error: any) {
                        connections.delete(data.chat_id);
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: getErrorMessage(error.message),
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    }
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'ALREADY_JOINED',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'leave_call':
                if (connection) {
                    if (data.type !== 'kicked_from_group') {
                        let result = await connection.leave_call();
                        if(result != null){
                            if (result['result'] === 'OK') {
                                connections.delete(data.chat_id);
                                await binding.sendUpdate({
                                    action: 'update_request',
                                    result: 'LEFT_VOICE_CHAT',
                                    chat_id: data.chat_id,
                                    solver_id: data.solver_id,
                                });
                            } else {
                                connections.delete(data.chat_id);
                                await binding.sendUpdate({
                                    action: 'update_request',
                                    result: 'LEFT_VOICE_CHAT',
                                    error: result['result'],
                                    chat_id: data.chat_id,
                                    solver_id: data.solver_id,
                                });
                            }
                        }
                    } else {
                        connection.stop();
                        connections.delete(data.chat_id);
                    }
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'pause':
                if (connection) {
                    try {
                        await connection.pause();
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'PAUSED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } catch (e) {}
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'resume':
                if (connection) {
                    try {
                        await connection.resume();
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'RESUMED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } catch (e) {}
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'change_stream':
                if (connection) {
                    try {
                        await connection.changeStream(
                            data.stream_audio,
                            data.stream_video,
                            data.lip_sync,
                        );
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'CHANGED_STREAM',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    } catch (e) {
                        await binding.sendUpdate({
                            action: 'update_request',
                            result: 'STREAM_DELETED',
                            chat_id: data.chat_id,
                            solver_id: data.solver_id,
                        });
                    }
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'mute_stream':
                if (connection) {
                    connection.mute();
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'MUTED_STREAM',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'unmute_stream':
                if (connection) {
                    connection.unmute();
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'UNMUTED_STREAM',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                } else {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
            case 'played_time':
                if (connection) {
                    await binding.sendUpdate({
                        action: 'update_request',
                        result: 'PLAYED_TIME',
                        time: connection.getTime(),
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                } else {
                     await binding.sendUpdate({
                        action: 'update_request',
                        result: 'NOT_IN_GROUP_CALL',
                        chat_id: data.chat_id,
                        solver_id: data.solver_id,
                    });
                }
                break;
        }
        binding.resolveUpdate(data.chat_id, update_id);
    });
} */
