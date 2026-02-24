package nbt

import (
    "bytes"
    "compress/gzip"
    "encoding/binary"
    "fmt"
    "io"
    "math"
)

// TagType 表示NBT标签类型
type TagType byte

const (
    TagEnd       TagType = 0x00
    TagByte      TagType = 0x01
    TagShort     TagType = 0x02
    TagInt       TagType = 0x03
    TagLong      TagType = 0x04
    TagFloat     TagType = 0x05
    TagDouble    TagType = 0x06
    TagByteArray TagType = 0x07
    TagString    TagType = 0x08
    TagList      TagType = 0x09
    TagCompound  TagType = 0x0a
    TagIntArray  TagType = 0x0b
    TagLongArray TagType = 0x0c
)

// NBTValue 表示NBT值
type NBTValue interface {
    Write(w io.Writer, tagType TagType) error
}

// WriteString 写入NBT字符串
func WriteString(w io.Writer, s string) error {
    if len(s) > math.MaxUint16 {
        return fmt.Errorf("string too long")
    }
    length := uint16(len(s))
    if err := binary.Write(w, binary.BigEndian, length); err != nil {
        return err
    }
    _, err := w.Write([]byte(s))
    return err
}

// WriteByteArray 写入字节数组
func WriteByteArray(w io.Writer, data []byte) error {
    length := int32(len(data))
    if err := binary.Write(w, binary.BigEndian, length); err != nil {
        return err
    }
    _, err := w.Write(data)
    return err
}

// WriteCompound 写入复合标签
func WriteCompound(w io.Writer, name string, value map[string]interface{}) error {
    // 写入标签类型（复合标签）
    if _, err := w.Write([]byte{byte(TagCompound)}); err != nil {
        return err
    }
    
    // 写入名称
    if err := WriteString(w, name); err != nil {
        return err
    }
    
    // 写入子标签
    for key, v := range value {
        if err := WriteTag(w, key, v); err != nil {
            return err
        }
    }
    
    // 写入结束标签
    if _, err := w.Write([]byte{byte(TagEnd)}); err != nil {
        return err
    }
    
    return nil
}

// WriteTag 写入NBT标签
func WriteTag(w io.Writer, name string, value interface{}) error {
    switch v := value.(type) {
    case int8:
        if _, err := w.Write([]byte{byte(TagByte)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case int16:
        if _, err := w.Write([]byte{byte(TagShort)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case int32:
        if _, err := w.Write([]byte{byte(TagInt)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case int64:
        if _, err := w.Write([]byte{byte(TagLong)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case float32:
        if _, err := w.Write([]byte{byte(TagFloat)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case float64:
        if _, err := w.Write([]byte{byte(TagDouble)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return binary.Write(w, binary.BigEndian, v)
    case []byte:
        if _, err := w.Write([]byte{byte(TagByteArray)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return WriteByteArray(w, v)
    case string:
        if _, err := w.Write([]byte{byte(TagString)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        return WriteString(w, v)
    case []int32:
        // 写入Int数组标签
        if _, err := w.Write([]byte{byte(TagIntArray)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        
        length := int32(len(v))
        if err := binary.Write(w, binary.BigEndian, length); err != nil {
            return err
        }
        
        for _, item := range v {
            if err := binary.Write(w, binary.BigEndian, item); err != nil {
                return err
            }
        }
        
        return nil
    case []interface{}:
        if _, err := w.Write([]byte{byte(TagList)}); err != nil {
            return err
        }
        if err := WriteString(w, name); err != nil {
            return err
        }
        
        if len(v) == 0 {
            // 如果列表为空，写入TagEnd作为类型标识
            if _, err := w.Write([]byte{byte(TagEnd)}); err != nil {
                return err
            }
            return binary.Write(w, binary.BigEndian, int32(0))
        }
        
        // 假设列表中的所有元素类型相同
        firstType := getTagType(v[0])
        if _, err := w.Write([]byte{byte(firstType)}); err != nil {
            return err
        }
        if err := binary.Write(w, binary.BigEndian, int32(len(v))); err != nil {
            return err
        }
        
        for _, item := range v {
            if err := WriteTagValue(w, firstType, item); err != nil {
                return err
            }
        }
        
        return nil
    case map[string]interface{}:
        return WriteCompound(w, name, v)
    default:
        return fmt.Errorf("unsupported type: %T", value)
    }
}

// getTagType 获取值对应的标签类型
func getTagType(value interface{}) TagType {
    switch value.(type) {
    case int8:
        return TagByte
    case int16:
        return TagShort
    case int32:
        return TagInt
    case int64:
        return TagLong
    case float32:
        return TagFloat
    case float64:
        return TagDouble
    case []byte:
        return TagByteArray
    case string:
        return TagString
    case []int32:
        return TagIntArray
    case []interface{}:
        return TagList
    case map[string]interface{}:
        return TagCompound
    default:
        return TagEnd
    }
}

// WriteTagValue 写入标签值
func WriteTagValue(w io.Writer, tagType TagType, value interface{}) error {
    switch tagType {
    case TagByte:
        return binary.Write(w, binary.BigEndian, value.(int8))
    case TagShort:
        return binary.Write(w, binary.BigEndian, value.(int16))
    case TagInt:
        return binary.Write(w, binary.BigEndian, value.(int32))
    case TagLong:
        return binary.Write(w, binary.BigEndian, value.(int64))
    case TagFloat:
        return binary.Write(w, binary.BigEndian, value.(float32))
    case TagDouble:
        return binary.Write(w, binary.BigEndian, value.(float64))
    case TagByteArray:
        return WriteByteArray(w, value.([]byte))
    case TagString:
        return WriteString(w, value.(string))
    case TagList:
        // 处理列表元素
        list := value.([]interface{})
        if len(list) == 0 {
            return nil
        }
        firstType := getTagType(list[0])
        for _, item := range list {
            if err := WriteTagValue(w, firstType, item); err != nil {
                return err
            }
        }
        return nil
    case TagCompound:
        // 处理复合标签
        comp := value.(map[string]interface{})
        for key, val := range comp {
            if err := WriteTag(w, key, val); err != nil {
                return err
            }
        }
        // 写入结束标签
        _, err := w.Write([]byte{byte(TagEnd)})
        return err
    default:
        return fmt.Errorf("unsupported tag type: %d", tagType)
    }
}

// WriteNBTToGzip 将NBT数据写入gzip压缩的文件
func WriteNBTToGzip(w io.Writer, name string, value map[string]interface{}) error {
    var buf bytes.Buffer
    
    // 写入NBT数据
    if err := WriteTag(&buf, name, value); err != nil {
        return err
    }
    
    // 使用gzip压缩
    gzWriter := gzip.NewWriter(w)
    defer gzWriter.Close()
    
    _, err := buf.WriteTo(gzWriter)
    return err
}