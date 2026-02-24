package nbt

import (
	"compress/gzip"
	"encoding/binary"
	"fmt"
	"io"
)

// ReadNBTFromGzip 从gzip压缩的文件中读取NBT数据
func ReadNBTFromGzip(r io.Reader) (map[string]interface{}, error) {
	// 创建gzip读取器
	gzReader, err := gzip.NewReader(r)
	if err != nil {
		return nil, err
	}
	defer gzReader.Close()

	// 读取标签类型
	var tagType byte
	if err := binary.Read(gzReader, binary.BigEndian, &tagType); err != nil {
		return nil, err
	}

	if TagType(tagType) != TagCompound {
		return nil, fmt.Errorf("expected compound tag, got %d", tagType)
	}

	// 读取名称
	var nameLen uint16
	if err := binary.Read(gzReader, binary.BigEndian, &nameLen); err != nil {
		return nil, err
	}

	nameBytes := make([]byte, nameLen)
	if _, err := io.ReadFull(gzReader, nameBytes); err != nil {
		return nil, err
	}

	// 读取复合标签内容
	compound, err := readCompoundValue(gzReader)
	if err != nil {
		return nil, err
	}

	return compound, nil
}

// readCompoundValue 读取复合标签的值
func readCompoundValue(r io.Reader) (map[string]interface{}, error) {
	compound := make(map[string]interface{})

	for {
		// 读取标签类型
		var tagType byte
		if err := binary.Read(r, binary.BigEndian, &tagType); err != nil {
			return nil, err
		}

		// 如果是结束标签，退出循环
		if TagType(tagType) == TagEnd {
			break
		}

		// 读取标签名称
		var nameLen uint16
		if err := binary.Read(r, binary.BigEndian, &nameLen); err != nil {
			return nil, err
		}

		nameBytes := make([]byte, nameLen)
		if _, err := io.ReadFull(r, nameBytes); err != nil {
			return nil, err
		}

		name := string(nameBytes)

		// 读取标签值
		value, err := readTagValue(r, TagType(tagType))
		if err != nil {
			return nil, err
		}

		compound[name] = value
	}

	return compound, nil
}

// readTagValue 读取标签值
func readTagValue(r io.Reader, tagType TagType) (interface{}, error) {
	switch tagType {
	case TagByte:
		var value int8
		err := binary.Read(r, binary.BigEndian, &value)
		return value, err
	case TagShort:
		var value int16
		err := binary.Read(r, binary.BigEndian, &value)
		return value, err
	case TagInt:
		var value int32
		err := binary.Read(r, binary.BigEndian, &value)
		return value, err
	case TagLong:
		// 读取两个int32作为int64
		var high, low int32
		if err := binary.Read(r, binary.BigEndian, &high); err != nil {
			return nil, err
		}
		if err := binary.Read(r, binary.BigEndian, &low); err != nil {
			return nil, err
		}
		return (int64(high) << 32) | int64(uint32(low)), nil
	case TagFloat:
		var value float32
		err := binary.Read(r, binary.BigEndian, &value)
		return value, err
	case TagDouble:
		var value float64
		err := binary.Read(r, binary.BigEndian, &value)
		return value, err
	case TagByteArray:
		// 读取数组长度
		var length int32
		if err := binary.Read(r, binary.BigEndian, &length); err != nil {
			return nil, err
		}

		if length < 0 {
			return nil, fmt.Errorf("negative array length: %d", length)
		}

		// 读取数组内容
		array := make([]byte, length)
		_, err := io.ReadFull(r, array)
		return array, err
	case TagString:
		// 读取字符串长度
		var length uint16
		if err := binary.Read(r, binary.BigEndian, &length); err != nil {
			return nil, err
		}

		// 读取字符串内容
		bytes := make([]byte, length)
		_, err := io.ReadFull(r, bytes)
		return string(bytes), err
	case TagList:
		return readListValue(r)
	case TagCompound:
		return readCompoundValue(r)
	case TagIntArray:
		// 读取数组长度
		var length int32
		if err := binary.Read(r, binary.BigEndian, &length); err != nil {
			return nil, err
		}

		if length < 0 {
			return nil, fmt.Errorf("negative array length: %d", length)
		}

		// 读取数组内容
		array := make([]int32, length)
		for i := int32(0); i < length; i++ {
			if err := binary.Read(r, binary.BigEndian, &array[i]); err != nil {
				return nil, err
			}
		}
		return array, nil
	default:
		return nil, fmt.Errorf("unsupported tag type: %d", tagType)
	}
}

// readListValue 读取列表值
func readListValue(r io.Reader) (interface{}, error) {
	// 读取元素类型
	var elemType byte
	if err := binary.Read(r, binary.BigEndian, &elemType); err != nil {
		return nil, err
	}

	// 读取列表长度
	var length int32
	if err := binary.Read(r, binary.BigEndian, &length); err != nil {
		return nil, err
	}

	if length < 0 {
		return nil, fmt.Errorf("negative list length: %d", length)
	}

	// 读取所有元素
	list := make([]interface{}, length)
	for i := int32(0); i < length; i++ {
		value, err := readTagValue(r, TagType(elemType))
		if err != nil {
			return nil, err
		}
		list[i] = value
	}

	return list, nil
}